import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import urllib.parse

# 1. 페이지 설정 및 모바일 웹 앱 최적화
st.set_page_config(page_title="부동산 v59 Mobile", layout="centered")

# 사용자 구글 시트 ID 및 GID 설정
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"

# --- 구글 시트 CSV 익스포트 로드 함수 ---
def load_cloud_data(ws_name, cols):
    try:
        # 사용자님이 알려주신 GID 반영
        gid_map = {
            "apart": "0", 
            "real": "1725468681",  # 반영 완료
            "hoga": "1366546489"   # 반영 완료
        }
        
        gid = gid_map.get(ws_name, "0")
        # 인증 오류를 피하기 위한 export URL 형식
        export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
        
        # 데이터 읽기 (네트워크 오류 대비)
        df = pd.read_csv(export_url)
        
        # 필수 컬럼 전처리 및 데이터 클리닝
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        df['표시'] = df['표시'].fillna(True)
        # 숫자가 0.0으로 표시되는 현상 방지
        for col in ['동', '층', '세대수', '연식']:
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', '0.0'], '')
        
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 연동 실패 (GID 확인 필요): {e}")
        return pd.DataFrame(columns=cols)

# --- 데이터 구조 정의 ---
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

# 세션 상태에 데이터 로딩
if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- 모바일 UI 스타일링 ---
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3rem; border-radius: 10px; font-weight: bold; margin-bottom: 5px; }
    .stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: bold; height: 45px; }
    .css-1r6slb0 { padding: 1rem 0.5rem; } /* 모바일 여백 최적화 */
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v59")

tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📊 시세데이터", "🏠 단지목록"])

with tab1:
    st.info("💡 서울/수도권 12.5억 이하 아파트 분석")
    
    # 지도 중심 설정 (서울 중심)
    m = folium.Map(
        location=[37.5665, 126.9780], zoom_start=11, min_zoom=10, max_bounds=True,
        min_lat=37.0, max_lat=38.3, min_lon=126.4, max_lon=127.7
    )
    folium.LatLngPopup().add_to(m)

    # 데이터가 있을 때만 마커 생성
    if not st.session_state.complex_df.empty:
        for _, row in st.session_state.complex_df.iterrows():
            try:
                if pd.notnull(row['위도']) and str(row['위도']).strip() != "":
                    lat, lon = float(row['위도']), float(row['경도'])
                    n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(str(row['아파트명']))}"
                    popup_html = f"""
                    <div style='width:150px; font-size:13px;'>
                        <b>{row['아파트명']}</b><br>
                        <a href='{n_link}' target='_blank' style='color:#03c75a; font-weight:bold; text-decoration:none;'>[N] 네이버 매물보기</a>
                    </div>
                    """
                    folium.Marker(
                        [lat, lon], 
                        popup=folium.Popup(popup_html, max_width=200),
                        icon=folium.Icon(color="blue", icon="home")
                    ).add_to(m)
            except:
                continue

    st_folium(m, width="100%", height=450, key="main_map")
    
    if st.button("🔄 데이터 최신화 (새로고침)"):
        st.cache_data.clear()
        st.rerun()

with tab2:
    st.subheader("📊 실거래 및 호가 현황")
    st.caption("구글 시트의 real, hoga 탭 데이터를 실시간으로 보여줍니다.")
    
    st.write("📈 **최근 실거래 기록**")
    st.dataframe(st.session_state.sales_df, use_container_width=True, hide_index=True)
    
    st.write("💰 **현재 매물 호가**")
    st.dataframe(st.session_state.hoga_df, use_container_width=True, hide_index=True)

with tab3:
    st.subheader("🏠 등록 단지 리스트")
    if not st.session_state.complex_df.empty:
        st.dataframe(
            st.session_state.complex_df[['아파트명', '세대수', '연식', '부동산전화번호']], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.write("등록된 단지가 없습니다.")
