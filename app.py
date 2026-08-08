import streamlit as st
import pandas as pd
import io
import requests
import asyncio
import xml.etree.ElementTree as ET
from pssapi import PssApiClient

st.set_page_config(page_title="ピクセル宇宙戦艦 エリアA プレイヤー分析", layout="wide")

st.title("🚀 ピクセル宇宙戦艦（Pixel Starships）トーナメント エリアA 分析")
st.caption("上位6艦隊の全所属メンバーデータを個別に取得して表示します。")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

async def get_pss_token_async():
    """pssapi公式クライアントを使用して正しいアクセストークンを発行"""
    client = PssApiClient()
    # デバイスログインを実行してログインオブジェクトを取得
    login_info = await client.device_service.device_login_11(
        checksum="",
        device_type="DeviceTypeAndroid",
        language_key="en",
        advertising_key="",
        client_date_time=""
    )
    return getattr(login_info, 'access_token', None) or getattr(login_info, 'token', None)

def fetch_area_a_with_debug():
    logs = []
    
    # ----------------------------------------------------
    # STEP 1: 正しい認証フローによるアクセストークン取得
    # ----------------------------------------------------
    logs.append("--- 🔑 STEP 1: アクセストークン取得 ---")
    token = None
    try:
        token = asyncio.run(get_pss_token_async())
        if token:
            logs.append(f"✅ トークン発行成功: {token[:12]}...")
        else:
            logs.append("❌ トークン発行失敗: レスポンスが空です")
    except Exception as e:
        logs.append(f"❌ トークン発行例外: {e}")

    # ----------------------------------------------------
    # STEP 2: 上位6艦隊の取得
    # ----------------------------------------------------
    logs.append("\n--- 🏆 STEP 2: 上位6艦隊データ取得 ---")
    alliances_url = "https://api.pixelstarships.com/AllianceService/ListAlliancesByRanking?take=6"
    if token:
        alliances_url += f"&accessToken={token}"
        
    try:
        a_res = requests.get(alliances_url, headers=HEADERS, timeout=10)
        logs.append(f"ランキング取得 HTTPステータス: {a_res.status_code}")
        
        if a_res.status_code != 200:
            return pd.DataFrame(), logs
            
        a_root = ET.fromstring(a_res.content)
        
        alliance_elems = [
            elem for elem in a_root.iter() 
            if 'allianceid' in {k.lower(): v for k, v in elem.attrib.items()}
        ]
        
        unique_alliances = []
        seen_ids = set()
        for elem in alliance_elems:
            attrs = {k.lower(): v for k, v in elem.attrib.items()}
            a_id = attrs.get('allianceid')
            if a_id and a_id not in seen_ids:
                seen_ids.add(a_id)
                a_name = elem.attrib.get('AllianceName') or attrs.get('alliancename') or f"艦隊_{a_id}"
                unique_alliances.append((a_id, a_name))
                
        logs.append(f"✅ 取得された上位艦隊数: {len(unique_alliances)}件")
        for idx, (a_id, a_name) in enumerate(unique_alliances[:6], 1):
            logs.append(f"  └ 順位 {idx}: {a_name} (ID: {a_id})")
            
    except Exception as e:
        logs.append(f"❌ ランキング取得例外: {e}")
        return pd.DataFrame(), logs

    # ----------------------------------------------------
    # STEP 3: 各艦隊のメンバー情報取得
    # ----------------------------------------------------
    logs.append("\n--- 👥 STEP 3: メンバーデータ取得・解析 ---")
    all_members = []
    
    for rank, (alliance_id, alliance_name) in enumerate(unique_alliances[:6], 1):
        users_url = f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={alliance_id}"
        if token:
            users_url += f"&accessToken={token}"
            
        try:
            u_res = requests.get(users_url, headers=HEADERS, timeout=10)
            if u_res.status_code == 200:
                u_root = ET.fromstring(u_res.content)
                
                # 属性に 'name' を持つ全ユーザー要素を検索
                user_elems = [
                    elem for elem in u_root.iter()
                    if 'name' in {k.lower(): v for k, v in elem.attrib.items()} and elem.tag != u_root.tag
                ]
                
                count = 0
                for u_elem in user_elems:
                    attrs = {k.lower(): v for k, v in u_elem.attrib.items()}
                    
                    if 'alliancename' in attrs:
                        continue
                        
                    name = u_elem.attrib.get('Name') or attrs.get('name') or '不明'
                    score = attrs.get('alliancescore') or attrs.get('score') or '0'
                    trophy = attrs.get('trophy') or '0'
                    membership = attrs.get('alliancemembership') or attrs.get('role') or '-'
                    user_id = attrs.get('id') or attrs.get('userid') or '-'
                    
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
                logs.append(f"❌ 【{alliance_name}】: HTTPエラー {u_res.status_code}")
        except Exception as err:
            logs.append(f"❌ 【{alliance_name}】: 解析例外 ({err})")
            
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
        with st.spinner("STEP 1〜3 を順次実行中..."):
            try:
                df_result, logs = fetch_area_a_with_debug()
                st.session_state.area_a_df = df_result
                st.session_state.fetch_logs = logs
                
                if not df_result.empty:
                    st.success("✅ 全ステップ完了！データをロードしました。")
                else:
                    st.error("データの取得結果が空でした。以下のデバッグログをご確認ください。")
            except Exception as e:
                st.error(f"実行中にエラーが発生しました: {e}")

# デバッグログの表示
if st.session_state.fetch_logs:
    with st.expander("🔍 ステップ別デバッグログを確認する", expanded=True):
        st.code("\n".join(st.session_state.fetch_logs), language="text")

# ----------------------------------------------------
# データ表示エリア
# ----------------------------------------------------
df = st.session_state.area_a_df

if not df.empty:
    st.markdown("---")
    st.subheader("📊 エリアA メンバーデータ一覧")
    
    fleet_names = list(df['艦隊名'].unique())
    selected_fleet = st.selectbox("📌 艦隊で絞り込む:", ["すべての艦隊 (全メンバー)"] + fleet_names)
    
    if selected_fleet == "すべての艦隊 (全メンバー)":
        display_df = df
    else:
        display_df = df[df['艦隊名'] == selected_fleet]
        
    st.info(f"表示中: **{len(display_df)} 名** | 合計スター数: **{display_df['スター数'].sum():,}**")
    
    st.dataframe(
        display_df.sort_values(by=["艦隊順位", "スター数"], ascending=[True, False]),
        use_container_width=True
    )
    
    st.markdown("---")
    search_name = st.text_input("🔍 プレイヤー名で直接検索:")
    if search_name:
        matched_df = df[df['プレイヤー名'].astype(str).str.contains(search_name, case=False, na=False)]
        if not matched_df.empty:
            st.dataframe(matched_df, use_container_width=True)
        else:
            st.warning("指定した名前のプレイヤーは見つかりませんでした。")

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