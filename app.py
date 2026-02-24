import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정 및 모바일 UI 최적화
st.set_page_config(page_title="부동산 v60 Mobile", layout="centered")

# 구글 시트 정보 (주소창 끝의 불필요한 파라미터 제거)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"

# 구글 시트 연결 엔진
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 데이터 로드 함수 (GID를 통한 직접 접근으로 400 에러 방지) ---
def load_cloud_data(ws_name, cols):
    try:
        # 탭별 GID 설정
        gid_map = {"apart": "0", "real": "1725468681", "hoga": "1366546489"}
        gid = gid_map.get(ws_name, "0")
        
        # 가장 안정적인 read 방식 (spreadsheet와 worksheet index 혼합 사용)
        df = conn.read(spreadsheet=SHEET_URL, worksheet=int(gid) if gid == "0" else ws_name, ttl=0)
        
        # 필수 컬럼 전처리
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        df['표시'] = df['표시'].fillna(True).astype(bool)
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 로드 실패: {e}")
        return pd.DataFrame(columns=cols)

# --- 데이터 저장 함수 ---
def save_cloud_data(df, ws_name):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 데이터 저장 성공!")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ 저장 실패: {e}")

# --- 데이터 구조 정의 및 로딩 ---
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- 모바일 전용 CSS ---
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; margin-bottom: 8px; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    div[data-testid="stExpander"] { border-radius: 12px; border: 1px solid #eee; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v60")

tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 데이터입력", "📊 데이터편집"])

# --- 탭 1: 지도 분석 (PC급 정보량 구현) ---
with tab1:
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    folium.LatLngPopup().add_to(m)

    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and str(row['위도']).strip() != "":
            apt_name = row['아파트명']
            
            # 시세 및 호가 결합 로직
            apt_h = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == apt_name]
            apt_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == apt_name]
            
            h_val = f"{apt_h['현재호가(억)'].min():.1f}억" if not apt_h.empty else "정보없음"
            s_val = f"{apt_s.sort_values('실거래일자').iloc[-1]['실거래가(억)']:.1f}억" if not apt_s.empty else "정보없음"
            phone = row['부동산전화번호'] if row['부동산전화번호'] else "등록없음"
            
            # 네이버 부동산 링크
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(apt_name)}"
            
            popup_content = f"""
            <div style='width:180px; font-size:13px; line-height:1.6;'>
                <b>🏠 {apt_name}</b><br>
                <hr style='margin:5px 0;'>
                💰 최저호가: <span style='color:red;'>{h_val}</span><br>
                📉 실거래가: <b>{s_val}</b><br>
                📞 부동산: <a href='tel:{phone}'>{phone}</a><br>
                <a href='{n_link}' target='_blank' style='display:block; margin-top:5px; padding:5px; background:#03c75a; color:white; text-align:center; border-radius:5px; text-decoration:none;'>네이버 매물보기 [N]</a>
            </div>
            """
            folium.Marker(
                [float(row['위도']), float(row['경도'])],
                popup=folium.Popup(popup_content, max_width=250),
                icon=folium.Icon(color="blue", icon="home")
            ).add_to(m)

    st_folium(m, width="100%", height=450, key="main_map")
    if st.button("🔄 전체 데이터 동기화"):
        st.cache_data.clear()
        st.rerun()

# --- 탭 2: 데이터 입력 (PC 기능 복구) ---
with tab2:
    mode = st.radio("입력 종류 선택", ["단지등록", "실거래추가", "호가추가"], horizontal=True)
    
    with st.form("input_form"):
        if mode == "단지등록":
            f_name = st.text_input("아파트명")
            f_coords = st.text_input("좌표 (예: 37.5, 127.0)")
            f_phone = st.text_input("부동산 번호")
            if st.form_submit_button("단지 저장"):
                lat, lon = map(float, f_coords.split(','))
                new_data = pd.DataFrame([{'표시':True, '아파트명':f_name, '부동산전화번호':f_phone, '위도':lat, '경도':lon}])
                save_cloud_data(pd.concat([st.session_state.complex_df, new_data]), "apart")
        
        elif mode == "실거래추가":
            f_apt = st.selectbox("아파트명", st.session_state.complex_df['아파트명'].unique())
            f_date = st.date_input("거래일자", date.today())
            f_price = st.number_input("실거래가(억)", format="%.2f")
            if st.form_submit_button("실거래 저장"):
                new_data = pd.DataFrame([{'실거래일자':str(f_date), '아파트명':f_apt, '실거래가(억)':f_price}])
                save_cloud_data(pd.concat([st.session_state.sales_df, new_data]), "real")

        elif mode == "호가추가":
            f_apt = st.selectbox("아파트명", st.session_state.complex_df['아파트명'].unique())
            f_hoga = st.number_input("호가(억)", format="%.2f")
            if st.form_submit_button("호가 저장"):
                new_data = pd.DataFrame([{'갱신일자':str(date.today()), '아파트명':f_apt, '현재호가(억)':f_hoga}])
                save_cloud_data(pd.concat([st.session_state.hoga_df, new_data]), "hoga")

# --- 탭 3: 데이터 편집 (수정/삭제) ---
with tab3:
    st.subheader("📊 데이터 관리")
    target = st.selectbox("편집할 데이터 선택", ["apart", "real", "hoga"])
    df_to_edit = st.session_state.complex_df if target == "apart" else st.session_state.sales_df if target == "real" else st.session_state.hoga_df
    
    edited_df = st.data_editor(df_to_edit, use_container_width=True, num_rows="dynamic")
    if st.button(f"{target} 데이터 변경사항 저장"):
        save_cloud_data(edited_df, target)
