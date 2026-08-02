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
# データ取得処理
# ----------------------------------------------------
async def get_top6_alliances():
    """上位6艦隊を取得"""
    client = PssApiClient()
    alliances = await client.alliance_service.list_alliances_by_ranking(0, 6)
    return alliances

def fetch_area_a_members():
    # 1. pssapiで上位6艦隊を取得
    alliances = asyncio.run(get_top6_alliances())
    
    all_members = []
    # サーバー拒否を避けるための詳細なヘッダー設定
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/xml, text/xml, */*'
    }
    
    logs = []
    
    for rank, alliance in enumerate(alliances, 1):
        # アライアンスIDを取得
        alliance_id = str(getattr(alliance, 'alliance_id', None) or getattr(alliance, 'id', ''))
        alliance_name = str(getattr(alliance, 'alliance_name', f"艦隊_{alliance_id}"))
        
        if not alliance_id or alliance_id == 'None':
            continue
            
        # 2. 艦隊ごとの所属ユーザー一覧を取得するエンドポイント
        url = f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={alliance_id}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                # XML要素のパース
                root = ET.fromstring(res.content)
                
                # PSS APIのXML階層（Userタグを探す）
                users = root.findall('.//User')
                if not users:
                    users = root.findall('.//UserSubquery')
                
                for user in users:
                    # 属性の取得（大文字小文字の両方に対応）
                    name = user.get('Name') or user.get('name') or '不明'
                    score = user.get('AllianceScore') or user.get('allianceScore') or '0'
                    trophy = user.get('Trophy') or user.get('trophy') or '0'
                    membership = user.get('AllianceMembership') or user.get('allianceMembership') or '-'
                    user_id = user.get('Id') or user.get('id') or '-'
                    
                    all_members.append({
                        "艦隊順位": rank,
                        "艦隊名": alliance_name,
                        "プレイヤー名": name,
                        "スター数": int(score) if str(score).isdigit() else 0,
                        "トロフィー": int(trophy) if str(trophy).isdigit() else 0,
                        "役職": membership,
                        "プレイヤーID": user_id
                    })
                logs.append(f"✅ {alliance_name}: {len(users)}名のデータ取得完了")
            else:
                logs.append(f"❌ {alliance_name}: HTTPエラー {res.status_code}")
        except Exception as err:
            logs.append(f"❌ {alliance_name}: 通信エラー ({err})")
            
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
        with st.spinner("上位6艦隊の全メンバーデータを取得中...（約5秒）"):
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

# 通信ログの表示（折りたたみ）
if st.session_state.fetch_logs:
    with st.expander("🔍 通信・取得ログを確認"):
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