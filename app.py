import streamlit as st
import pandas as pd
import asyncio
import io
import requests
import xml.etree.ElementTree as ET
from pssapi import PssApiClient

st.set_page_config(page_title="PSS API 応答構造診断", layout="wide")

st.title("🔬 Pixel Starships API 構造解析・診断モード")
st.caption("実際のAPIレスポンスXMLの中身を確認し、正しい解析パターンを特定します。")

async def get_top_alliance():
    client = PssApiClient()
    alliances = await client.alliance_service.list_alliances_by_ranking(0, 1)
    return alliances[0] if alliances else None

if st.button("🔍 1位艦隊のデータ構造をテスト取得", type="primary"):
    with st.spinner("APIから生レスポンスを取得中..."):
        top_alliance = asyncio.run(get_top_alliance())
        
        if top_alliance:
            a_id = str(getattr(top_alliance, 'alliance_id', None) or getattr(top_alliance, 'id', ''))
            a_name = str(getattr(top_alliance, 'alliance_name', ''))
            st.success(f"1位艦隊: **{a_name}** (ID: `{a_id}`)")
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            
            # テストするAPIエンドポイント候補
            urls = {
                "パターンA (ListUsers)": f"https://api.pixelstarships.com/AllianceService/ListUsers?allianceId={a_id}",
                "パターンB (ListUsersWithDesign)": f"https://api.pixelstarships.com/AllianceService/ListUsersWithDesign?allianceId={a_id}",
                "パターンC (GetAlliance)": f"https://api.pixelstarships.com/AllianceService/GetAlliance?allianceId={a_id}"
            }
            
            for key, url in urls.items():
                st.markdown(f"### 📡 {key}")
                try:
                    res = requests.get(url, headers=headers, timeout=10)
                    st.code(f"HTTP Status: {res.status_code}")
                    if res.status_code == 200:
                        # XMLの先頭500文字を表示
                        st.text_area(f"{key} のレスポンス生データ (XML)", res.text[:1000], height=150)
                    else:
                        st.error("取得失敗")
                except Exception as e:
                    st.error(f"エラー: {e}")
        else:
            st.error("1位艦隊の取得に失敗しました。")