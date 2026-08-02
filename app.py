import streamlit as st
import pandas as pd
import asyncio
import io
from pssapi import PssApiClient

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）トーナメント エリアA 分析")
st.caption("上位6艦隊の全所属メンバーデータを個別に取得して表示します。")

# ----------------------------------------------------
# データ取得処理（pssapiで完結）
# ----------------------------------------------------
async def get_data_async():
    client = PssApiClient()
    
    # 1. 上位6艦隊を取得
    alliances = await client.alliance_service.list_alliances_by_ranking(0, 6)
    
    all_members = []
    
    for rank, alliance in enumerate(alliances, 1):
        alliance_id = getattr(alliance, 'alliance_id', None)
        alliance_name = getattr(alliance, 'alliance_name', f"艦隊_{alliance_id}")
        
        if not alliance_id:
            continue
            
        # 2. 艦隊詳細情報を取得（ここに所属ユーザー一覧が含まれる仕様）
        alliance_full = await client.alliance_service.get_alliance(alliance_id)
        
        # メンバー一覧を取り出す
        users = getattr(alliance_full, 'users', []) or getattr(alliance, 'users', [])
        
        for user in users:
            all_members.append({
                "艦隊順位": rank,
                "艦隊名": alliance_name,
                "プレイヤー名": getattr(user, 'name', '不明'),
                "スター数": getattr(user, 'alliance_score', 0),
                "トロフィー": getattr(user, 'trophy', 0),
                "役職": getattr(user, 'alliance_membership', '-'),
                "プレイヤーID": getattr(user, 'id', '-')
            })
            
    return pd.DataFrame(all_members)

def fetch_area_a_members():
    # Streamlit環境で安全に非同期関数を実行
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_data_async())
    finally:
        loop.close()

# ----------------------------------------------------
# 画面操作＆データ読み込み
# ----------------------------------------------------
st.markdown("---")
st.subheader("🔄 データ取得操作")

if "area_a_df" not in st.session_state:
    st.session_state.area_a_df = pd.DataFrame()

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🚀 エリアA（上位6艦隊）の最新データを取得", type="primary"):
        with st.spinner("上位6艦隊の全メンバーデータを取得中..."):
            try:
                df_result = fetch_area_a_members()
                st.session_state.area_a_df = df_result
                if not df_result.empty:
                    st.success("✅ データ取得が完了しました！")
                else:
                    st.error("取得できたメンバーデータが0件でした。")
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