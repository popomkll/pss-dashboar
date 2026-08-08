import io
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー＆PVP分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）エリアA & 対戦分析")
st.caption("PSS公式APIと連携して、メンバーデータおよびPVP対戦ログを取得・分析します。")

HEADERS = {"User-Agent": "PixelStarships/1.0"}

# ----------------------------------------------------
# セッション状態の初期化
# ----------------------------------------------------
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "area_a_df" not in st.session_state:
    st.session_state.area_a_df = pd.DataFrame()
if "pvp_df" not in st.session_state:
    st.session_state.pvp_df = pd.DataFrame()


# ----------------------------------------------------
# API通信関数
# ----------------------------------------------------
def login_with_email(email, password):
    """複数のエンドポイント候補を順に試して正規トークンを取得"""
    # 試行対象のログイン用エンドポイント一覧
    endpoints = [
        "https://api.pixelstarships.com/UserService/UserEmailPasswordLogin",
        "https://api.pixelstarships.com/UserService/EmailPasswordLogin",
        "https://api.pixelstarships.com/UserService/UserEmailPasswordAuthorize",
        "https://api.pixelstarships.com/UserService/EmailPasswordAuthorize",
    ]

    params = {
        "email": email,
        "password": password,
        "deviceType": "DeviceTypeAndroid",
    }

    last_error = ""

    for url in endpoints:
        api_name = url.split("/")[-1]
        try:
            res = requests.get(url, params=params, headers=HEADERS, timeout=10)

            if res.status_code == 200:
                root = ET.fromstring(res.content)

                # xml内から accessToken を探索
                token = None
                for elem in root.iter():
                    token = elem.attrib.get("accessToken") or elem.attrib.get("AccessToken")
                    if token:
                        break

                if token:
                    return token, f"✅ ログイン成功！ ({api_name})"

                # 認証失敗（パスワード違い等）のメッセージ取得
                error_msg = (
                    root.attrib.get("errorMessage")
                    or root.attrib.get("error")
                    or "認証失敗: メールアドレスまたはパスワードを確認してください"
                )
                return None, f"❌ {error_msg} ({api_name})"
            else:
                last_error = f"HTTP {res.status_code} ({api_name})"
        except Exception as e:
            last_error = f"通信例外: {e} ({api_name})"

    return None, f"❌ 接続エラー: {last_error}"


def fetch_area_a_members(token):
    """上位6艦隊とそのメンバー一覧を取得"""
    logs = []
    alliances_url = f"https://api.pixelstarships.com/AllianceService/ListAlliancesByRanking?take=6&accessToken={token}"

    try:
        a_res = requests.get(alliances_url, headers=HEADERS, timeout=10)
        if a_res.status_code != 200:
            return pd.DataFrame(), [f"❌ ランキング取得失敗: HTTP {a_res.status_code}"]

        a_root = ET.fromstring(a_res.content)
        unique_alliances = []
        seen_ids = set()

        for elem in a_root.iter():
            attrs = {k.lower(): v for k, v in elem.attrib.items()}
            a_id = attrs.get("allianceid")
            if a_id and a_id not in seen_ids:
                seen_ids.add(a_id)
                a_name = elem.attrib.get("AllianceName") or attrs.get("alliancename") or f"艦隊_{a_id}"
                unique_alliances.append((a_id, a_name))

        all_members = []
        for rank, (alliance_id, alliance_name) in enumerate(unique_alliances[:6], 1):
            users_url = f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={alliance_id}&accessToken={token}"
            u_res = requests.get(users_url, headers=HEADERS, timeout=10)

            if u_res.status_code == 200:
                u_root = ET.fromstring(u_res.content)
                user_elems = [
                    elem
                    for elem in u_root.iter()
                    if "name" in {k.lower(): v for k, v in elem.attrib.items()} and elem.tag != u_root.tag
                ]

                count = 0
                for u_elem in user_elems:
                    attrs = {k.lower(): v for k, v in u_elem.attrib.items()}
                    if "alliancename" in attrs:
                        continue

                    name = u_elem.attrib.get("Name") or attrs.get("name") or "不明"
                    score = attrs.get("alliancescore") or attrs.get("score") or "0"
                    trophy = attrs.get("trophy") or "0"
                    membership = attrs.get("alliancemembership") or attrs.get("role") or "-"
                    user_id = attrs.get("id") or attrs.get("userid") or "-"

                    all_members.append(
                        {
                            "艦隊順位": rank,
                            "艦隊名": alliance_name,
                            "プレイヤー名": name,
                            "スター数": int(score) if str(score).isdigit() else 0,
                            "トロフィー": int(trophy) if str(trophy).isdigit() else 0,
                            "役職": membership,
                            "プレイヤーID": user_id,
                        }
                    )
                    count += 1
                logs.append(f"✅ 【{alliance_name}】: {count}名 取得完了")
            else:
                logs.append(f"❌ 【{alliance_name}】: HTTP {u_res.status_code}")

        return pd.DataFrame(all_members), logs
    except Exception as e:
        return pd.DataFrame(), [f"❌ 例外発生: {e}"]


def fetch_pvp_logs(token):
    """PVP（対戦成績）ログの取得"""
    url = f"https://api.pixelstarships.com/UserService/ListPvpLogs?accessToken={token}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            pvp_list = []
            for log in root.findall(".//PvpLog"):
                pvp_list.append(
                    {
                        "対戦日時": log.attrib.get("Date", "")[:19].replace("T", " "),
                        "攻撃者": log.attrib.get("AttackerName", "不明"),
                        "防衛者": log.attrib.get("DefenderName", "不明"),
                        "獲得スター": log.attrib.get("StarCount", "0"),
                        "結果タイプ": log.attrib.get("DisasterType", "-"),
                    }
                )
            return pd.DataFrame(pvp_list), f"✅ PVPログ {len(pvp_list)} 件取得完了"
        else:
            return pd.DataFrame(), f"❌ PVPログ取得エラー: HTTP {res.status_code}"
    except Exception as e:
        return pd.DataFrame(), f"❌ PVPログ通信エラー: {e}"


# ----------------------------------------------------
# サイドバー：アカウント認証エリア
# ----------------------------------------------------
st.sidebar.header("🔑 PSS ログイン設定")
st.sidebar.caption("メンバー詳細やPVPログの取得には正規ログインが必要です。")

email_input = st.sidebar.text_input("メールアドレス")
password_input = st.sidebar.text_input("パスワード", type="password")

if st.sidebar.button("ログインしてトークン取得"):
    if email_input and password_input:
        with st.sidebar.spinner("認証中..."):
            token, msg = login_with_email(email_input, password_input)
            if token:
                st.session_state.access_token = token
                st.sidebar.success(msg)
            else:
                st.sidebar.error(msg)
    else:
        st.sidebar.warning("メールアドレスとパスワードを入力してください。")

# トークンの状態表示
if st.session_state.access_token:
    st.sidebar.info(f"🔑 トークン保持中: `{st.session_state.access_token[:10]}...`")
else:
    st.sidebar.warning("⚠️ 未ログイン状態です（データが取得できません）。")


# ----------------------------------------------------
# メイン画面：タブ切り替え構成
# ----------------------------------------------------
tab1, tab2 = st.tabs(["🏆 エリアA 艦隊・メンバー分析", "⚔️ PVP対戦成績ログ"])

# --- TAB 1: メンバー分析 ---
with tab1:
    st.subheader("🔄 エリアA（上位6艦隊）メンバー情報取得")

    if st.button("🚀 メンバーデータを更新・取得", type="primary"):
        if not st.session_state.access_token:
            st.error("サイドバーから先にログインを行ってください。")
        else:
            with st.spinner("上位6艦隊と所属メンバーデータを取得中..."):
                df_res, logs = fetch_area_a_members(st.session_state.access_token)
                st.session_state.area_a_df = df_res
                st.write("\n".join(logs))

    df_m = st.session_state.area_a_df
    if not df_m.empty:
        st.markdown("---")
        fleet_names = list(df_m["艦隊名"].unique())
        selected_fleet = st.selectbox("📌 艦隊で絞り込む:", ["すべての艦隊 (全メンバー)"] + fleet_names)

        display_df = df_m if selected_fleet == "すべての艦隊 (全メンバー)" else df_m[df_m["艦隊名"] == selected_fleet]
        st.info(f"表示中: **{len(display_df)} 名** | 合計スター数: **{display_df['スター数'].sum():,}**")

        st.dataframe(
            display_df.sort_values(by=["艦隊順位", "スター数"], ascending=[True, False]),
            use_container_width=True,
        )

        # Excelダウンロード
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_m.to_excel(writer, index=False, sheet_name="エリアAメンバー")
        st.download_button(
            label="📥 全メンバーデータをExcelでダウンロード",
            data=output.getvalue(),
            file_name="PSS_AreaA_Members.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

# --- TAB 2: PVP対戦ログ ---
with tab2:
    st.subheader("⚔️ 直近のPVP対戦成績取得")

    if st.button("🔄 PVPログを取得"):
        if not st.session_state.access_token:
            st.error("サイドバーから先にログインを行ってください。")
        else:
            with st.spinner("PVPログを取得中..."):
                pvp_res, pvp_msg = fetch_pvp_logs(st.session_state.access_token)
                st.session_state.pvp_df = pvp_res
                if not pvp_res.empty:
                    st.success(pvp_msg)
                else:
                    st.warning(pvp_msg)

    df_pvp = st.session_state.pvp_df
    if not df_pvp.empty:
        st.dataframe(df_pvp, use_container_width=True)