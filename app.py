import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정
st.set_page_config(page_title="부동산 v73 Tracking", layout="centered")

# 구글 시트 정보 및 연결
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 세션 상태 초기화 ---
if 'clicked_coords' not in st.session_state: st.session_state.clicked_coords = ""

# --- 데이터 로드 함수 ---
def load_cloud_data(ws_name, cols):
    try:
        gid_map = {"apart": "0", "real": "1725468681", "hoga": "1366546489"}
        export_url = f"{SHEET_URL}/export?format=csv&gid={gid_map.get(ws_name, '0')}"
        df = pd.read_csv(export_url)
        if '표시' not in df.columns: df.insert(0, '표시', True)
        
        num_cols = ['위도', '경도', '현재호가(억)', '실거래가(억)', '호가변동', '변동액', '세대수', '연식']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        for c in cols:
            if c not in df.columns: df[c] = ""
            
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 로드 실패")
        return pd.DataFrame(columns=cols)

# --- 데이터 저장 함수 ---
def save_cloud_data(df, ws_name):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 시트와 실시간 동기화 완료!")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ 저장 실패: {e}")

# 컬럼 정의
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

# 데이터 로딩
if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- 스타일링 ---
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v73")
tab1, tab2, tab3 = st.tabs(["📍 지도", "📝 정보입력", "📊 데이터관리"])

# --- 탭 1: 지도 (기능 유지) ---
with tab1:
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    # [지도 표시 로직은 v72와 동일하게 마커/팝업 구성]
    # (코드 중략: v72의 마커 렌더링 부분)
    map_data = st_folium(m, width="100%", height=500, key="main_map")
    if map_data and map_data.get("last_clicked"):
        st.session_state.clicked_coords = f"{map_data['last_clicked']['lat']:.6f}, {map_data['last_clicked']['lng']:.6f}"
        st.success(f"📍 좌표 선택됨: {st.session_state.clicked_coords}")

# --- 탭 2: 정보 입력 (신규/기존 선택 및 자동 계산) ---
with tab2:
    mode = st.radio("입력 종류", ["단지등록", "실거래추가", "호가추가"], horizontal=True)
    
    with st.form("input_v73"):
        if mode == "단지등록":
            f_name = st.text_input("아파트명")
            c1, c2 = st.columns(2)
            f_gen = c1.number_input("세대수", step=1)
            f_year = c2.number_input("연식(년)", step=1, value=2020)
            f_coords = st.text_input("좌표 (위도, 경도)", value=st.session_state.clicked_coords)
            f_phone = st.text_input("부동산전화번호")
            if st.form_submit_button("🏙️ 단지 저장"):
                if f_name and f_coords:
                    lat, lon = map(float, f_coords.split(','))
                    new_row = pd.DataFrame([{'표시':True, '아파트명':f_name, '세대수':f_gen, '연식':f_year, '부동산전화번호':f_phone, '위도':lat, '경도':lon}])
                    save_cloud_data(pd.concat([st.session_state.complex_df, new_row]), "apart")
                else: st.warning("필수 항목 확인")

        elif mode == "실거래추가":
            f_date = st.date_input("실거래일자", value=date.today())
            f_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
            f_size = st.text_input("평형(m2)")
            f_price = st.number_input("실거래가(억)", format="%.2f")
            
            # 이전 실거래가 찾아서 변동액 자동 계산
            prev_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == f_apt].sort_values('실거래일자')
            last_price = prev_s['실거래가(억)'].iloc[-1] if not prev_s.empty else f_price
            f_diff = f_price - last_price

            if st.form_submit_button("💰 실거래 저장 (자동계산)"):
                new_row = pd.DataFrame([{'실거래일자':str(f_date), '아파트명':f_apt, '평형(m2)':f_size, '실거래가(억)':f_price, '변동액':f_diff}])
                save_cloud_data(pd.concat([st.session_state.sales_df, new_row]), "real")

        elif mode == "호가추가":
            h_type = st.radio("등록 유형", ["기존매물 추적", "신규매물 등록"], horizontal=True)
            f_up_date = st.date_input("갱신일자", value=date.today())
            f_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
            
            if h_type == "기존매물 추적":
                # 기존 시트에서 해당 아파트의 매물 리스트(동/층/평형) 추출
                existing_items = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == f_apt]
                if not existing_items.empty:
                    item_options = existing_items.apply(lambda x: f"{x['동']}동 {x['층']}층 ({x['평형(m2)']}m2)", axis=1).unique()
                    target_item = st.selectbox("추적할 매물 선택", item_options)
                    
                    # 선택된 매물의 이전 호가 찾기
                    sel_dong = target_item.split('동')[0]
                    f_size = target_item.split('(')[1].split('m2')[0]
                    prev_h_val = existing_items[existing_items['동'] == sel_dong]['현재호가(억)'].iloc[-1]
                    st.caption(f"이전 호가: {prev_h_val}억")
                    
                    f_dong = sel_dong
                    f_floor = target_item.split('동 ')[1].split('층')[0]
                else:
                    st.warning("등록된 기존 매물이 없습니다. 신규매물 등록을 이용하세요.")
                    f_dong, f_floor, f_size, prev_h_val = "", "", "", 0.0
            else:
                c1, c2, c3 = st.columns(3)
                f_dong = c1.text_input("동")
                f_floor = c2.text_input("층")
                f_size = c3.text_input("평형(m2)")
                prev_h_val = 0.0

            f_hoga = st.number_input("신규 호가(억)", format="%.2f")
            # 변동액은 자동 계산 (신규 등록 시 0)
            f_hdiff = f_hoga - prev_h_val if prev_h_val > 0 else 0.0

            if st.form_submit_button("📢 호가 동기화 저장"):
                new_row = pd.DataFrame([{'갱신일자':str(f_up_date), '아파트명':f_apt, '평형(m2)':f_size, '동':f_dong, '층':f_floor, '현재호가(억)':f_hoga, '호가변동':f_hdiff}])
                save_cloud_data(pd.concat([st.session_state.hoga_df, new_row]), "hoga")

# --- 탭 3: 데이터 관리 ---
with tab3:
    target = st.selectbox("시트 선택", ["apart", "real", "hoga"])
    edited_df = st.data_editor(st.session_state[f"{target}_df"], use_container_width=True, num_rows="dynamic")
    if st.button("💾 구글 시트 일괄 저장"):
        save_cloud_data(edited_df, target)
