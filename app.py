import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import urllib.parse

# 1. 페이지 설정 및 모바일 최적화 [cite: 2026-02-24]
st.set_page_config(page_title="부동산 v59 Mobile", layout="centered")

# [반영 완료] 사용자님의 구글 시트 기본 ID
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"

# --- [최종 해결] 구글 API 연결 대신 CSV 내보내기 주소 사용 --- [cite: 2026-02-24]
def load_cloud_data(ws_name, cols):
    try:
        # 탭별 고유 GID 설정 (apart=0, real/hoga는 시트에서 확인 가능하나 순서대로 시도)
        # 만약 real, hoga 탭이 인식이 안 되면 시트 주소창 끝의 gid=숫자를 아래에 적어주세요.
        gid_map = {"apart": "0", "real": "787034451", "hoga": "1738740266"} # 예시 GID입니다. [cite: 2026-02-24]
        
        gid = gid_map.get(ws_name, "0")
        export_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
        
        # 주소로부터 직접 데이터프레임 생성 [cite: 2026-02-24]
        df = pd.read_csv(export_url)
        
        # 필수 컬럼 전처리 [cite: 2026-02-24]
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        df['표시'] = df['표시'].fillna(True)
        # 문자열 변환 및 0.0 방지 [cite: 2026-02-24]
        for col in ['동', '층']:
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', '0.0'], '')
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 로드 실패: {e}")
        return pd.DataFrame(columns=cols)

# --- 데이터 구조 정의 --- [cite: 2026-02-24]
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

# 데이터 로딩 (세션 상태 유지) [cite: 2026-02-24]
if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- 모바일 전용 UI 스타일 --- [cite: 2026-02-24]
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v59")

tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 신규등록", "📊 시세관리"])

with tab1:
    # v58 범례 적용 (12.5억 기준) [cite: 2026-02-11, 2026-02-24]
    st.markdown("""<div style="background-color: #f9f9f9; padding: 10px; border-radius: 10px; border: 1px solid #ddd; font-size: 12px;">
        <b>📍 예산 12.5억 기준</b> | <span style="color:blue;">●</span> 갭내 | <span style="color:red;">●</span> 초과
    </div>""", unsafe_allow_html=True)
    
    # v58 수도권 철벽 고정 지도 [cite: 2026-02-24]
    m = folium.Map(
        location=[37.5665, 126.9780], zoom_start=11, min_zoom=10, max_bounds=True,
        min_lat=37.0, max_lat=38.3, min_lon=126.4, max_lon=127.7
    )
    m.add_child(folium.LatLngPopup())

    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and row['위도'] != "":
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(str(row['아파트명']))}"
            popup_html = f"<b>{row['아파트명']}</b><br><a href='{n_link}' target='_blank'>네이버부동산 [N]</a>"
            folium.Marker(
                [float(row['위도']), float(row['경도'])], 
                popup=folium.Popup(popup_html, max_width=200),
                icon=folium.Icon(color="blue", icon="home")
            ).add_to(m)

    st_folium(m, width="100%", height=450, key="main_map")
    if st.button("🔄 데이터 강제 새로고침"):
        st.cache_data.clear()
        st.rerun()

with tab2:
    st.subheader("📝 단지 신규 등록")
    st.warning("⚠️ 모바일 CSV 모드에서는 조회를 우선 지원합니다. 등록 기능은 PC 버전 사용을 권장합니다.")
    # (등록 로직은 CSV 쓰기 권한 설정이 복잡하므로 PC 버전에서 수행하시길 추천드립니다.) [cite: 2026-02-05]

with tab3:
    st.subheader("📊 시세 데이터 확인")
    target_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
    st.write(f"🏠 **{target_apt}** 실거래 정보")
    st.dataframe(st.session_state.sales_df[st.session_state.sales_df['아파트명'] == target_apt], use_container_width=True)
