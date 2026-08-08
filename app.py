import streamlit as st
import pandas as pd
import io
import requests
import re
import xml.etree.ElementTree as ET

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）トーナメント エリアA 分析")
st.caption("上位6艦隊の全所属メンバーデータを個別に取得して表示します。")

# ----------------------------------------------------
# PSS API 通信 ＆ 強力文字列解析ロジック
# ----------------------------------------------------
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def get_access_token():
    url = "https://api.pixelstarships.com/DeviceService/DeviceLogin11?deviceType=DeviceTypeAndroid"
    try:
        res = requests.post(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            match = re.search(r'accessToken="([^"]+)"', res.text) or re.search(r'token="([^"]+)"', res.text)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None

def fetch_area_a_members():
    token = get_access_token()
    
    alliances_url = "https://api.pixelstarships.com/AllianceService/ListAlliancesByRanking?take=6"
    if token:
        alliances_url += f"&accessToken={token}"
        
    res = requests.get(alliances_url, headers=HEADERS, timeout=10)
    if res.status_code != 200:
        return pd.DataFrame(), [f"艦隊ランキング取得失敗: HTTP {res.status_code}"]
        
    # 正規表現で Alliance タグ情報を直接抽出
    alliance_matches = re.findall(r'<Alliance[^>]+>', res.text)
    
    all_members = []
    logs = []
    
    for rank, a_str in enumerate(alliance_matches[:6], 1):
        a_id_m = re.search(r'AllianceId="([^"]+)"', a_str, re.I) or re.search(r'Id="([^"]+)"', a_str, re.I)
        a_name_m = re.search(r'AllianceName="([^"]+)"', a_str, re.I) or re.search(r'Name="([^"]+)"', a_str, re.I)
        
        alliance_id = a_id_m.group(1) if a_id_m else None
        alliance_name = a_name_m.group(1) if a_name_m else f"艦隊_{alliance_id}"
        
        if not alliance_id:
            continue
            
        users_url = f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={alliance_id}"
        if token:
            users_url += f"&accessToken={token}"
            
        try:
            u_res = requests.get(users_url, headers=HEADERS, timeout=10)
            if u_res.status_code == 200:
                # User情報を正規表現で一括取得（タグ名不問）
                user_matches = re.findall(r'<[a-zA-Z0-9]+[^>]+Name="[^"]+"[^>]*>', u_res.text)
                if not user_matches:
                    # 小文字の場合の検索パターン
                    user_matches = re.findall(r'<[a-zA-Z0-9]+[^>]+name="[^"]+"[^>]*>', u_res.text)
                
                count = 0
                for u_str in user_matches:
                    # アライアンス自体のタグを誤検知した場合はスキップ
                    if '<Alliance' in u_str:
                        continue
                        
                    name_m = re.search(r'Name="([^"]+)"', u_str, re.I)
                    score_m = re.search(r'AllianceScore="([^"]+)"', u_str, re.I) or re.search(r'Score="([^"]+)"', u_str, re.I)
                    trophy_m = re.search(r'Trophy="([^"]+)"', u_str, re.I)
                    membership_m = re.search(r'AllianceMembership="([^"]+)"', u_str, re.I) or re.search(r'Role="([^"]+)"', u_str, re.I)
                    id_m = re.search(r'Id="([^"]+)"', u_str, re.I) or re.search(r'UserId="([^"]+)"', u_str, re.I)
                    
                    name = name_m.group(1) if name_m else "不明"
                    score = score_m.group(1) if score_m else "0"
                    trophy = trophy_m.group(1) if trophy_m else "0"
                    membership = membership_m.group(1) if membership_m else "-"
                    user_id = id_m.group(1) if id_m else "-"
                    
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
                    
                logs.append(f"✅ {alliance_name}: {count}名 取得成功")
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
        with st.spinner("PSS公式サーバーからデータを解析・抽出中...（約3〜5秒）"):
            try:
                df_result, logs = fetch_area_a_members()
                st.session_state.area_a_df = df_result
                st.session_state.fetch_logs = logs
                
                if not df_result.empty:
                    st.success("✅ データ取得が完了しました！")
                else:
                    st.error("データの取得結果が空でした。詳細ログをご確認ください。")
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