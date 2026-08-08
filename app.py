import streamlit as st
import pandas as pd
import io
import requests
import xml.etree.ElementTree as ET

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）トーナメント エリアA 分析")
st.caption("上位6艦隊の全所属メンバーデータを個別に取得して表示します。")

# ----------------------------------------------------
# PSS API 直接通信処理（ライブラリ不使用）
# ----------------------------------------------------
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def get_access_token():
    """デバイスログインを実行してaccessTokenを取得"""
    url = "https://api.pixelstarships.com/DeviceService/DeviceLogin11?deviceType=DeviceTypeAndroid"
    try:
        res = requests.post(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            # Login要素からaccessTokenを取得
            login_elem = root.find('.//DeviceLogin') or root.find('.//Login') or root
            token = login_elem.get('accessToken') or login_elem.get('token')
            return token
    except Exception as e:
        st.write(f"トークン取得エラー: {e}")
    return None

def fetch_area_a_members():
    # 1. アクセストークンを取得
    token = get_access_token()
    
    # 2. 上位艦隊一覧（Rankings）を取得
    alliances_url = "https://api.pixelstarships.com/AllianceService/ListAlliancesByRanking?take=6"
    if token:
        alliances_url += f"&accessToken={token}"
        
    res = requests.get(alliances_url, headers=HEADERS, timeout=10)
    if res.status_code != 200:
        return pd.DataFrame(), [f"艦隊ランキング取得失敗: HTTP {res.status_code}"]
        
    root = ET.fromstring(res.content)
    alliances = root.findall('.//Alliance')
    if not alliances:
        alliances = [elem for elem in root.iter() if 'alliancename' in {k.lower(): v for k, v in elem.attrib.items()}]
        
    all_members = []
    logs = []
    
    # 3. 各艦隊のメンバーを取得
    for rank, alliance in enumerate(alliances[:6], 1):
        attrs = {k.lower(): v for k, v in alliance.attrib.items()}
        alliance_id = attrs.get('allianceid') or attrs.get('id')
        alliance_name = alliance.attrib.get('AllianceName') or attrs.get('alliancename') or f"艦隊_{alliance_id}"
        
        if not alliance_id:
            continue
            
        users_url = f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={alliance_id}"
        if token:
            users_url += f"&accessToken={token}"
            
        try:
            u_res = requests.get(users_url, headers=HEADERS, timeout=10)
            if u_res.status_code == 200:
                u_root = ET.fromstring(u_res.content)
                users = u_root.findall('.//User')
                if not users:
                    users = [elem for elem in u_root.iter() if 'name' in {k.lower(): v for k, v in elem.attrib.items()}]
                    
                for user in users:
                    u_attrs = {k.lower(): v for k, v in user.attrib.items()}
                    name = user.attrib.get('Name') or u_attrs.get('name') or '不明'
                    score = u_attrs.get('alliancescore') or u_attrs.get('score') or '0'
                    trophy = u_attrs.get('trophy') or '0'
                    membership = u_attrs.get('alliancemembership') or u_attrs.get('role') or '-'
                    user_id = u_attrs.get('id') or u_attrs.get('userid') or '-'
                    
                    all_members.append({
                        "艦隊順位": rank,
                        "艦隊名": alliance_name,
                        "プレイヤー名": name,
                        "スター数": int(score) if str(score).isdigit() else 0,
                        "トロフィー": int(trophy) if str(trophy).isdigit() else 0,
                        "役職": membership,
                        "プレイヤーID": user_id
                    })
                logs.append(f"✅ {alliance_name}: {len(users)}名 取得成功")
            else:
                logs.append(f"❌ {alliance_name}: HTTP {u_res.status_code}")
        except Exception as err:
            logs.append(f"❌ {alliance_name}: {err}")
            
    return pd.DataFrame(all_members), logs

# ----------------------------------------------------
# 画面操作＆データ読み込み
# ----------------------------------------------------
st.markdown("---")
st.subheader("🔄 データ取得操作")

if "area_a_df" not in st.session_state:
    st.session_state.area_a_df = pd.DataFrame()
if "fetch_logs" not in st.session_state:
    st.session_state.fetch_logs = []

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🚀 エリアA（上位6艦隊）の最新データを取得", type="primary"):
        with st.spinner("PSS公式サーバーからデータを直接取得中...（約3〜5秒）"):
            try:
                df_result, logs = fetch_area_a_members()
                st.session_state.area_a_df = df_result
                st.session_state.fetch_logs = logs
                
                if not df_result.empty:
                    st.success("✅ データ取得が完了しました！")
                else:
                    st.error("データの取得結果が空でした。通信ログをご確認ください。")
            except Exception as e:
                st.error(f"実行中にエラーが発生しました: {e}")

# 通信ログの表示
if st.session_state.fetch_logs:
    with st.expander("🔍 詳細ログを確認"):
        for log in st.session_state.fetch_logs:
            st.write(log)

# ----------------------------------------------------
# データ表示エリア
# ----------------------------------------------------
df = st.session_state.area_a_df

if not df.empty:
    st.markdown("---")
    st.subheader("📊 エリアA メンバーデータ一覧")
    
    # 艦隊ごとの絞り込み
    fleet_names = list(df['艦隊名'].unique())
    selected_fleet = st.selectbox("📌 艦隊で絞り込む:", ["すべての艦隊 (全メンバー)"] + fleet_names)
    
    if selected_fleet == "すべての艦隊 (全メンバー)":
        display_df = df
    else:
        display_df = df[df['艦隊名'] == selected_fleet]
        
    st.info(f"表示中: **{len(display_df)} 名** | 合計スター数: **{display_df['スター数'].sum():,}**")
    
    # テーブル表示
    st.dataframe(
        display_df.sort_values(by=["艦隊順位", "スター数"], ascending=[True, False]),
        use_container_width=True
    )
    
    # 検索機能
    st.markdown("---")
    search_name = st.text_input("🔍 プレイヤー名で直接検索:")
    if search_name:
        matched_df = df[df['プレイヤー名'].astype(str).str.contains(search_name, case=False, na=False)]
        if not matched_df.empty:
            st.dataframe(matched_df, use_container_width=True)
        else:
            st.warning("指定した名前のプレイヤーは見つかりませんでした。")

    # Excelダウンロード
    st.markdown("---")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='エリアAメンバー')
    
    st.download_button(
        label="📥 全メンバーデータをExcelでダウンロード",
        data=output.getvalue(),
        file_name="PSS_AreaA_Members.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("💡 上の「エリアA（上位6艦隊）の最新データを取得」ボタンを押すと、データを読み込みます。")