import io
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー＆PVP分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）エリアA & 対戦分析")
st.caption("PSS公式APIと連携して、メンバーデータおよびPVP対戦ログを取得・分析します。")

HEADERS = {
    "User-Agent": "PixelStarships/1.0",
    "Accept": "*/*"
}

# ----------------------------------------------------
# セッション状態の初期化
# ----------------------------------------------------
if "access_token" not in st.session_state:
    st.session_state.access_token = ""
if "area_a_df" not in st.session_state:
    st.session_state.area_a_df = pd.DataFrame()
if "pvp_df" not in st.session_state:
    st.session_state.pvp_df = pd.DataFrame()


# ----------------------------------------------------
# API通信関数（api2 / api の両対応フォールバック）
# ----------------------------------------------------
def fetch_api_data(endpoint_path, token):
    """api2.pixelstarships.com を優先し、ダメなら api.pixelstarships.com を試す"""
    hosts = ["https://api2.pixelstarships.com", "https://api.pixelstarships.com"]
    
    for host in hosts:
        url = f"{host}{endpoint_path}&accessToken={token}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200:
                return res.content, None
        except Exception as e:
            continue
            
    return None, "データ取得に失敗しました。トークンが正しいか、有効期限が切れていないか確認してください。"


def fetch_area_a_members(token):
    """上位6艦隊とそのメンバー一覧を取得"""
    logs = []
    xml_data, err = fetch_api_data("/AllianceService/ListAlliancesByRanking?take=6", token)
    
    if err:
        return pd.DataFrame(), [f"❌ ランキング取得エラー: {err}"]

    try:
        a_root = ET.fromstring(xml_data)
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
            u_xml, u_err = fetch_api_data(f"/AllianceService/ListUsers?allianceId={alliance_id}", token)

            if u_xml:
                u_root = ET.fromstring(u_xml)
                user_elems = [
                    elem for elem in u_root.iter()
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

                    all_members.append({
                        "艦隊順位": rank,
                        "艦隊名": alliance_name,
                        "プレイヤー名": name,
                        "スター数": int(score) if str(score).isdigit() else 0,
                        "トロフィー": int(trophy) if str(trophy).isdigit() else 0,
                        "役職": membership,
                        "プレイヤーID": user_id
                    })
                    count += 1
                logs.append(f"✅ 【{alliance_name}】: {count}名 取得完了")
            else:
                logs.append(f"❌ 【{alliance_name}】: 取得失敗")

        return pd.DataFrame(all_members), logs
    except Exception as e:
        return pd.DataFrame(), [f"❌ XML解析例外: {e}"]


def fetch_pvp_logs(token):
    """PVP（対戦成績）ログの取得"""
    xml_data, err = fetch_api_data("/UserService/ListPvpLogs?", token)
    if err:
        return pd.DataFrame(), f"❌ PVPログ取得エラー: {err}"

    try:
        root = ET.fromstring(xml_data)
        pvp_list = []
        for log in root.findall(".//PvpLog"):
            pvp_list.append({
                "対戦日時": log.attrib.get("Date", "")[:19].replace("T", " "),
                "攻撃者": log.attrib.get("AttackerName", "不明"),
                "防衛者": log.attrib.get("DefenderName", "不明"),
                "獲得スター": log.attrib.get("StarCount", "0"),
                "結果タイプ": log.attrib.get("DisasterType", "-")
            })
        return pd.DataFrame(pvp_list), f"✅ PVPログ {len(pvp_list)} 件取得完了"
    except Exception as e:
        return pd.DataFrame(), f"❌ PVPログ通信エラー: {e}"


# ----------------------------------------------------
# サイドバー：トークン設定エリア
# ----------------------------------------------------
st.sidebar.header("🔑 PSS アクセストークン設定")
st.sidebar.caption("API通信用のアクセストークンを入力してください。")

token_input = st.sidebar.text_input(
    "AccessToken（アクセストークン）",
    value=st.session_state.access_token,
    type="password",
    help="PSSのアクセストークン文字列を直接貼り付けます。"
)

if token_input:
    st.session_state.access_token = token_input.strip()

if st.session_state.access_token:
    st.sidebar.success("🔑 トークンが設定されています")
else:
    st.sidebar.warning("⚠️ トークン未設定です")

st.sidebar.markdown("---")
st.sidebar.subheader("💡 トークンの取得方法")
st.sidebar.markdown("""
以下の手順でトークンを簡単に取得できます：
1. **ブラウザで直接ログインURLを開く**
2. 画面に表示されるXMLの中から `accessToken="xxxx..."` の部分をコピー
3. 上の入力欄に貼り付け
""")

# ----------------------------------------------------
# メイン画面：タブ切り替え構成
# ----------------------------------------------------
tab1, tab2 = st.tabs(["🏆 エリアA 艦隊・メンバー分析", "⚔️ PVP対戦成績ログ"])

# --- TAB 1: メンバー分析 ---
with tab1:
    st.subheader("🔄 エリアA（上位6艦隊）メンバー情報取得")

    if st.button("🚀 メンバーデータを更新・取得", type="primary"):
        if not st.session_state.access_token:
            st.error("サイドバーにアクセストークンを入力してください。")
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
            use_container_width=True
        )

        # Excelダウンロード
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_m.to_excel(writer, index=False, sheet_name="エリアAメンバー")
        st.download_button(
            label="📥 全メンバーデータをExcelでダウンロード",
            data=output.getvalue(),
            file_name="PSS_AreaA_Members.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- TAB 2: PVP対戦ログ ---
with tab2:
    st.subheader("⚔️ 直近のPVP対戦成績取得")

    if st.button("🔄 PVPログを取得"):
        if not st.session_state.access_token:
            st.error("サイドバーにアクセストークンを入力してください。")
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