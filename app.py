import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import io

st.set_page_config(page_title="ピクセル宇宙戦艦 戦績ダッシュボード", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）戦績ダッシュボード")

# ----------------------------------------------------
# データ取得関数（公式API）
# ----------------------------------------------------
@st.cache_data(ttl=600)  # 10分ごとに自動更新
def fetch_alliance_ranking():
    """公式APIから上位艦隊（アライアンス）のランキングを取得"""
    url = "https://api.pixelstarships.com/AllianceService/ListAllAlliancesByRanking?take=100"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            fleets = []
            for alliance in root.findall('.//Alliance'):
                fleets.append({
                    "順位": int(alliance.get('Ranking', 0)) if alliance.get('Ranking') else "-",
                    "艦隊名": alliance.get('AllianceName', '不明'),
                    "スター数": int(alliance.get('Score', 0)),
                    "トロフィー": int(alliance.get('Trophy', 0)),
                    "メンバー数": int(alliance.get('NumberOfMembers', 0)),
                    "必須トロフィー": int(alliance.get('MinTrophyRequired', 0))
                })
            df = pd.DataFrame(fleets)
            if not df.empty and "順位" in df.columns:
                df = df.sort_values("スター数", ascending=False).reset_index(drop=True)
                df['順位'] = df.index + 1
            return df
    except Exception as e:
        st.error(f"公式APIからのデータ取得に失敗しました: {e}")
    return pd.DataFrame()

# ----------------------------------------------------
# Excelバックアップ読み込み関数（勝敗ログ用）
# ----------------------------------------------------
@st.cache_data
def load_excel_data(file):
    """手動管理のExcelファイル（対戦詳細ログ）を読み込む"""
    xls = pd.ExcelFile(file)
    all_data = []
    
    for sheet_name in xls.sheet_names:
        if sheet_name == 'ALL': continue
            
        df = pd.read_excel(file, sheet_name=sheet_name)
        if not df.empty and df.iloc[0, 0] == 'NAME':
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)
            
        new_cols = []
        detail_count = 1
        for col in df.columns:
            if pd.isna(col) or str(col).startswith('Unnamed:'):
                new_cols.append(f"対戦詳細_{detail_count}")
                detail_count += 1
            else:
                new_cols.append(str(col))
        df.columns = new_cols
        
        df['艦隊名'] = str(sheet_name)
        cols = list(df.columns)
        if '艦隊名' in cols:
            cols.remove('艦隊名')
            cols.insert(1, '艦隊名')
            df = df[cols]
            
        all_data.append(df)
        
    if all_data:
        full_df = pd.concat(all_data, ignore_index=True)
        return full_df.dropna(subset=['NAME'])
    return pd.DataFrame()

# ----------------------------------------------------
# メイン画面処理
# ----------------------------------------------------
st.sidebar.header("🌐 データソース切り替え")
mode = st.sidebar.radio("表示モード:", ["📡 公式API リアルタイムランキング", "📊 過去対戦ログ (Excel)"])

if mode == "📡 公式API リアルタイムランキング":
    st.subheader("🏆 公式アライアンス（艦隊）ランキング")
    with st.spinner("公式サーバーから最新データを自動取得中..."):
        api_df = fetch_alliance_ranking()
    
    if not api_df.empty:
        st.success(f"✅ 最新データを取得しました（自動更新: 10分毎 / データ件数: {len(api_df)}件）")
        
        # 艦隊名検索
        search_fleet = st.text_input("🔍 艦隊名で検索:")
        if search_fleet:
            filtered_df = api_df[api_df['艦隊名'].str.contains(search_fleet, case=False, na=False)]
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.dataframe(api_df, use_container_width=True)
            
        # Excelダウンロード
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            api_df.to_excel(writer, index=False, sheet_name='ランキング')
        
        st.download_button(
            label="📥 ランキングデータをExcelでダウンロード",
            data=output.getvalue(),
            file_name="PSS_Official_Ranking.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("現在、公式APIからのデータが取得できませんでした。時間をおいて再試行してください。")

else:
    st.subheader("📊 艦隊別 対戦詳細ログ")
    uploaded_file = st.sidebar.file_uploader("『Legend League.xlsx』をアップロード", type=["xlsx"])
    
    if uploaded_file:
        excel_df = load_excel_data(uploaded_file)
        if not excel_df.empty:
            st.success("✅ Excelログの読み込み完了")
            
            fleet_list = ["すべて"] + list(excel_df['艦隊名'].unique())
            selected_fleet = st.selectbox("表示する艦隊を選択:", fleet_list)
            
            display_df = excel_df if selected_fleet == "すべて" else excel_df[excel_df['艦隊名'] == selected_fleet]
            
            # 列名マッピング
            column_config = {}
            for col in display_df.columns:
                if str(col).startswith("対戦詳細_"):
                    column_config[col] = st.column_config.Column("対戦詳細")
                    
            st.dataframe(display_df, column_config=column_config, use_container_width=True)
            
            # 検索機能
            st.markdown("---")
            st.subheader("🔍 プレイヤー検索")
            search_name = st.text_input("プレイヤー名（NAME）を入力:")
            if search_name:
                matched = excel_df[excel_df['NAME'].astype(str).str.contains(search_name, case=False, na=False)]
                if not matched.empty:
                    st.dataframe(matched, column_config=column_config, use_container_width=True)
                else:
                    st.warning("一致するプレイヤーが見つかりませんでした。")
    else:
        st.info("👈 左のサイドバーから『Legend League.xlsx』をアップロードしてください。")