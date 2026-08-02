import streamlit as st
import pandas as pd
import asyncio
import io
import requests
import xml.etree.ElementTree as ET
from pssapi import PssApiClient

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）トーナメント エリアA 分析")
st.caption("上位6艦隊の全所属メンバーデータを個別に取得して表示します。")

# ----------------------------------------------------
# データ取得処理（上位6艦隊 ＆ 各メンバー詳細）
# ----------------------------------------------------
async def fetch_area_a_members():
    client = PssApiClient()
    
    # 1. 上位6艦隊を取得
    alliances = await client.alliance_service.list_alliances_by_ranking(0, 6)
    
    all_members = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for rank, alliance in enumerate(alliances, 1):
        alliance_id = getattr(alliance, 'alliance_id', 0)
        alliance_name = getattr(alliance, 'alliance_name', f"艦隊_{alliance_id}")
        
        # 2. 艦隊IDに紐づくメンバー一覧を公式APIから直接取得
        url = f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={alliance_id}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for user in root.findall('.//User'):
                    all_members.append({
                        "艦隊順位": rank,
                        "艦隊名": alliance_name,
                        "プレイヤー名": user.get('Name', '不明'),
                        "スター数": int(user.get('AllianceScore', 0)),
                        "トロフィー": int(user.get('Trophy', 0)),
                        "役職": user.get('AllianceMembership', '-'),
                        "プレイヤーID": user.get('Id', '-')
                    })
        except Exception as err:
            st.warning(f"艦隊「{alliance_name}」のメンバーデータ取得でスキップが発生しました: {err}")
            
    return pd.DataFrame(all_members)

# ----------------------------------------------------
# 画面操作＆データ読み込み
# ----------------------------------------------------
st.markdown("---")
st.subheader("🔄 データ取得操作")

# セッション状態の初期化
if "area_a_df" not in st.session_state:
    st.session_state.area_a_df = pd.DataFrame()

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🚀 エリアA（上位6艦隊）の最新データを取得", type="primary"):
        with st.spinner("上位6艦隊の全メンバーデータを取得中..."):
            try:
                df_result = asyncio.run(fetch_area_a_members())
                st.session_state.area_a_df = df_result
                if not df_result.empty:
                    st.success("✅ データ取得が完了しました！")
                else:
                    st.error("データの取得結果が空でした。")
            except Exception as e:
                st.error(f"データ取得中にエラーが発生しました: {e}")

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