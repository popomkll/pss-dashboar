import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Legend League 戦績ダッシュボード", layout="wide")

st.title("🏆 Legend League 戦績ダッシュボード")

# サイドバーでExcelファイルのアップロード
st.sidebar.header("📁 データ設定")
uploaded_file = st.sidebar.file_uploader("『Legend League.xlsx』をアップロードしてください", type=["xlsx"])

@st.cache_data
def load_data(file):
    xls = pd.ExcelFile(file)
    all_data = []
    
    for sheet_name in xls.sheet_names:
        if sheet_name == 'ALL':
            continue  # ALLシートは重複回避のため除外
            
        df = pd.read_excel(file, sheet_name=sheet_name)
        
        # ヘッダー行の補正 (0行目が NAME, star, WR になっている場合)
        if not df.empty and df.iloc[0, 0] == 'NAME':
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)
            
        # 内部処理用に一意な列名を割り当て（結合エラー・スタイルエラー回避のため番号付き）
        new_cols = []
        detail_count = 1
        for col in df.columns:
            if pd.isna(col) or str(col).startswith('Unnamed:'):
                new_cols.append(f"対戦詳細_{detail_count}")
                detail_count += 1
            else:
                new_cols.append(str(col))
        df.columns = new_cols
        
        # 艦隊名カラムを追加
        df['艦隊名'] = str(sheet_name)
        
        # 列順の並び替え：一番左端（0列目）に「艦隊名」を配置
        cols = list(df.columns)
        if '艦隊名' in cols:
            cols.remove('艦隊名')
            cols.insert(0, '艦隊名')  # 艦隊名 -> NAME -> star -> WR ...
            df = df[cols]
            
        all_data.append(df)
        
    if all_data:
        full_df = pd.concat(all_data, ignore_index=True)
        # プレイヤー名がない空行を除去
        full_df = full_df.dropna(subset=['NAME'])
        return full_df
    return pd.DataFrame()

# 🎨 スタイル設定（文字色変更・フォーマット）
def style_dataframe(df_to_style):
    styled_df = df_to_style.copy()
    
    # 1. WR（勝率）のフォーマット変更 (0.25 -> 25%, 1 -> 100%)
    if 'WR' in styled_df.columns:
        def format_wr(val):
            if pd.isna(val) or val == "":
                return ""
            try:
                val_float = float(val)
                return f"{val_float * 100:.0f}%"
            except:
                return str(val)
        styled_df['WR'] = styled_df['WR'].apply(format_wr)

    # 2. NaN / None を完全な空白文字に置き換え
    styled_df = styled_df.fillna("")

    # 3. 星の数（star）に応じた文字色（NAME と star 列に適用）
    def color_stars_and_names(row):
        styles = [''] * len(row)
        try:
            star_val = float(row['star']) if row['star'] != "" else 0
        except ValueError:
            star_val = 0

        # 色判定
        color_style = ''
        if star_val >= 600:
            color_style = 'color: #dc3545; font-weight: bold;'  # 赤文字（太字）
        elif 400 <= star_val <= 599:
            color_style = 'color: #0d6efd; font-weight: bold;'  # 青文字（太字）

        # NAME 列と star 列だけにスタイルを割り当てる
        if color_style:
            for i, col in enumerate(row.index):
                if col in ['NAME', 'star']:
                    styles[i] = color_style

        return styles

    # 行ごとにスタイル適用
    styler = styled_df.style.apply(color_stars_and_names, axis=1)
    return styler

# 画面表示用に列名マッピング（対戦詳細_1, 対戦詳細_2 などを「対戦詳細」として見せる）
def get_column_config(df_data):
    config = {}
    for col in df_data.columns:
        if str(col).startswith("対戦詳細_"):
            config[col] = st.column_config.Column("対戦詳細")
    return config

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    if not df.empty:
        st.success("✅ データを正常に読み込みました！")
        
        # ----------------------------------------------------
        # 1. 全体データの表示
        # ----------------------------------------------------
        st.subheader("📊 艦隊別 & 全体メンバー一覧")
        
        fleet_list = ["すべて"] + list(df['艦隊名'].unique())
        selected_fleet = st.selectbox("表示する艦隊を選択:", fleet_list)
        
        if selected_fleet != "すべて":
            display_df = df[df['艦隊名'] == selected_fleet]
        else:
            display_df = df
            
        st.dataframe(
            style_dataframe(display_df),
            column_config=get_column_config(display_df),
            use_container_width=True
        )
        
        # ----------------------------------------------------
        # 2. プレイヤー個別検索
        # ----------------------------------------------------
        st.markdown("---")
        st.subheader("🔍 プレイヤー個別検索 & 勝敗分析")
        
        search_name = st.text_input("プレイヤー名（NAME）を入力してください:")
        
        if search_name:
            matched_df = df[df['NAME'].astype(str).str.contains(search_name, case=False, na=False)]
            
            if not matched_df.empty:
                st.write(f"### 🎯 『{search_name}』 さんの検索結果")
                st.dataframe(
                    style_dataframe(matched_df),
                    column_config=get_column_config(matched_df),
                    use_container_width=True
                )
                
                # Excel出力用データ
                export_df = matched_df.copy()
                if 'WR' in export_df.columns:
                    export_df['WR'] = export_df['WR'].apply(
                        lambda x: f"{float(x)*100:.0f}%" if pd.notna(x) and isinstance(x, (int, float)) else x
                    )
                export_df = export_df.fillna("")

                # ダウンロード用Excelのヘッダー整形
                export_cols = []
                for col in export_df.columns:
                    if str(col).startswith("対戦詳細_"):
                        export_cols.append("対戦詳細")
                    else:
                        export_cols.append(col)
                export_df.columns = export_cols

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='検索結果')
                excel_bytes = output.getvalue()
                
                # 3. ダウンロードボタン
                st.download_button(
                    label="📥 この結果をExcelでダウンロード",
                    data=excel_bytes,
                    file_name=f"{search_name}_legend_league.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning(f"「{search_name}」 に一致するプレイヤーは見つかりませんでした。")
else:
    st.info("👈 左側のサイドバーから『Legend League.xlsx』をドラッグ＆ドロップしてください。")