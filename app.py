import streamlit as st
import pandas as pd
import asyncio
import io
from pssapi import PssApiClient

st.set_page_config(page_title="ピクセル宇宙戦艦 戦績ダッシュボード", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）公式ランキングダッシュボード")

# ----------------------------------------------------
# pssapi を使用した公式データ取得処理
# ----------------------------------------------------
async def fetch_alliance_ranking():
    client = PssApiClient()
    # PSS公式サーバーからアライアンス（艦隊）トップ100を取得
    alliances = await client.alliance_service.list_all_alliances_by_ranking(take=100)
    
    fleet_list = []
    for rank, alliance in enumerate(alliances, 1):
        fleet_list.append({
            "順位": rank,
            "艦隊名": alliance.alliance_name,
            "スター数": alliance.score,
            "トロフィー": alliance.trophy,
            "メンバー数": alliance.number_of_members,
            "アライアンスID": alliance.alliance_id
        })
    return pd.DataFrame(fleet_list)

@st.cache_data(ttl=600)  # 10分ごとにキャッシュを自動更新
def get_official_data():
    return asyncio.run(fetch_alliance_ranking())

# ----------------------------------------------------
# 画面表示処理
# ----------------------------------------------------
st.subheader("🏆 公式アライアンス（艦隊）リアルタイムランキング")

with st.spinner("PSS公式サーバーから最新データを自動取得中..."):
    try:
        df = get_official_data()
    except Exception as e:
        df = pd.DataFrame()
        st.error(f"公式データ取得中にエラーが発生しました: {e}")

if not df.empty:
    st.success(f"✅ 最新データを取得しました（全 {len(df)} 艦隊 / 10分毎に自動更新）")
    
    # 検索機能
    search_fleet = st.text_input("🔍 艦隊名で検索:")
    
    if search_fleet:
        display_df = df[df['艦隊名'].astype(str).str.contains(search_fleet, case=False, na=False)]
    else:
        display_df = df
        
    st.dataframe(display_df, use_container_width=True)
    
    # Excelダウンロード機能
    st.markdown("---")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='ランキング')
    
    st.download_button(
        label="📥 最新ランキングをExcelでダウンロード",
        data=output.getvalue(),
        file_name="PSS_Official_Ranking.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("現在、公式APIからデータを取得できませんでした。時間をおいてページを再読み込みしてください。")