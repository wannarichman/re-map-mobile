import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
from datetime import date
import urllib.parse

# 1. 페이지 설정 및 iOS 최적화
st.set_page_config(page_title="부동산 v59 Mobile", layout="centered")

# [핵심 수정] 400 에러 방지를 위한 최적화된 시트 주소 형식
SHEET_URL = "https://docs.google.com/spreadsheets/d/1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"

# 구글 시트 연결 엔진 설정
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 데이터 로드 및 저장 함수 (인식 오류 방지 로직 강화) ---
def load_cloud_data(ws_name, cols):
    try:
        # worksheet 이름으로 직접 호출하여 Bad Request 방지
        df = conn.read(spreadsheet=SHEET_URL, worksheet=ws_name, ttl=0)
        
        # 기본 컬럼 생성 및 데이터 전처리
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = True if c == '표시' else ""
        
        # 모바일 가독성 및 타입 변환
        df['표시'] = df['표시'].fillna(True).astype(bool)
        for col in ['동', '층']:
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', '0.0'], '')
        return df[cols]
    except Exception as e:
        # 에러 발생 시 사용자에게 탭 이름 확인 메시지 출력
        st.error(f"⚠️ '{ws_name}' 탭 연결 확인 필요: {e}")
        return pd.DataFrame(columns=cols)

def save_cloud_data(df, ws_name):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 저장 완료!")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ 저장 실패: {e}")

# --- v58 데이터 구조 정의 ---
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

# 세션 상태에 데이터 로딩
if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- 모바일 전용 CSS 디자인 ---
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; font-size: 16px; margin-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; height: 50px; }
    div[data-testid="stExpander"] { border-radius: 12px; border: 1px solid #eee; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v59")

tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 신규등록", "📊 시세관리"])

with tab1:
    # v58 범례 및 예산 로직 유지 (12.5억 기준)
    st.markdown("""<div style="background-color: #f9f9f9; padding: 10px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; font-size: 12px;">
        <b>📍 예산 12.5억 기준 범례</b><br>
        <span style="color:blue;">●</span> 갭 1.5억 내 | <span style="color:red;">●</span> 갭 초과 | <span style="color:orange;">★</span> 급매물
    </div>""", unsafe_allow_html=True)
    
    # [v58] 수도권 철벽 고정 지도 설정
    m = folium.Map(
        location=[37.5665, 126.9780], zoom_start=11, min_zoom=10, max_bounds=True,
        min_lat=37.0, max_lat=38.3, min_lon=126.4, max_lon=127.7
    )
    m.add_child(folium.LatLngPopup())

    visible_df = st.session_state.complex_df[st.session_state.complex_df['표시'] == True]
    for _, row in visible_df.iterrows():
        if pd.notnull(row['위도']) and row['위도'] != 0:
            apt_h = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == row['아파트명']]
            apt_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == row['아파트명']]
            color, icon = "gray", "home"
            h_txt, s_txt = "정보없음", "기록없음"
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(row['아파트명'])}"
            
            if not apt_h.empty:
                min_h = apt_h.loc[apt_h['현재호가(억)'].idxmin()]
                h_val, h_diff = min_h['현재호가(억)'], min_h['호가변동']
                hc = "red" if h_diff > 0 else "blue" if h_diff < 0 else "black"
                # v58 네이버 [N] 버튼 디자인
                h_txt = f"<b>{h_val:.1f}억</b> <a href='{n_link}' target='_blank' style='text-decoration:none; color:white; background-color:#03c75a; padding:1px 4px; border-radius:2px; font-size:10px; font-weight:bold;'>N</a>"
                color = "blue" if abs(h_val - 12.5) <= 1.5 else "red"
                if (apt_h['현재호가(억)'].mean() - h_val) >= 1.0: color, icon = "orange", "star"
                
                matched = apt_s[apt_s['평형(m2)'] == min_h['평형(m2)']]
                if not matched.empty:
                    ls = matched.sort_values('실거래일자').iloc[-1]
                    s_txt = f"{ls['실거래가(억)']:.1f}억 ({ls['실거래일자']})"

            popup_html = f"<div style='font-size:13px; line-height:1.5;'><b>{row['아파트명']}</b><br>최저호가: {h_txt}<br>실거래가: {s_txt}</div>"
            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(popup_html, max_width=200), icon=folium.Icon(color=color, icon=icon)).add_to(m)

    st_folium(m, width="100%", height=450, key="main_map")
    if st.button("🔄 데이터 강제 동기화"): st.rerun()

with tab2:
    st.subheader("📝 신규 단지 등록")
    with st.form("m_reg_form", clear_on_submit=True):
        m_apt = st.text_input("아파트명")
        m_coords = st.text_input("좌표 (지도 클릭 후 복사)")
        m_phone = st.text_input("부동산 연락처")
        if st.form_submit_button("클라우드 서버 등록"):
            try:
                lat_v, lon_v = map(float, m_coords.split(','))
                new_c = {'표시': True, '아파트명': m_apt, '세대수': 0, '연식': 2010, '부동산전화번호': m_phone, '위도': lat_v, '경도': lon_v}
                st.session_state.complex_df = pd.concat([st.session_state.complex_df, pd.DataFrame([new_c])], ignore_index=True)
                save_cloud_data(st.session_state.complex_df, "apart"); st.rerun()
            except: st.error("좌표 형식을 확인하세요.")

with tab3:
    target_apt = st.selectbox("관리 단지 선택", st.session_state.complex_df['아파트명'].unique() if not st.session_state.complex_df.empty else ["데이터 없음"])
    
    with st.expander("📊 실거래가 편집"):
        s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == target_apt]
        ed_s = st.data_editor(s_df, use_container_width=True, num_rows="dynamic", key="m_s_ed")
        if st.button("💾 실거래 데이터 저장"):
            save_cloud_data(pd.concat([st.session_state.sales_df[st.session_state.sales_df['아파트명'] != target_apt], ed_s]), "real"); st.rerun()

    with st.expander("📈 매물 호가 편집"):
        h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == target_apt]
        ed_h = st.data_editor(h_df, use_container_width=True, num_rows="dynamic", key="m_h_ed")
        if st.button("💾 호가 데이터 저장"):
            save_cloud_data(pd.concat([st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] != target_apt], ed_h]), "hoga"); st.rerun()
