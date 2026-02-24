import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정
st.set_page_config(page_title="부동산 v61 Mobile", layout="centered")

# 구글 시트 정보 [cite: 2026-02-24]
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

# 구글 시트 연결 엔진 (저장용) [cite: 2026-02-24]
conn = st.connection("gsheets", type=GSheetsConnection)

# --- [안정성 강화] 읽기는 CSV 익스포트 방식으로 강제 고정 --- [cite: 2026-02-24]
def load_cloud_data(ws_name, cols):
    try:
        # 사용자님이 확인해주신 GID 반영 [cite: 2026-02-24]
        gid_map = {"apart": "0", "real": "1725468681", "hoga": "1366546489"}
        gid = gid_map.get(ws_name, "0")
        export_url = f"{SHEET_URL}/export?format=csv&gid={gid}"
        
        # 주소로부터 직접 읽기 (400 에러 원천 차단) [cite: 2026-02-24]
        df = pd.read_csv(export_url)
        
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        df['표시'] = df['표시'].fillna(True)
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 로드 실패: {e}")
        return pd.DataFrame(columns=cols)

# --- 데이터 저장 함수 --- [cite: 2026-02-24]
def save_cloud_data(df, ws_name):
    try:
        # 저장은 API 방식을 사용 (편집자 권한 필요) [cite: 2026-02-24]
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 저장 성공! 5초 후 새로고침됩니다.")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ 저장 실패 (권한 또는 탭이름 확인): {e}")

# 데이터 로딩 [cite: 2026-02-24]
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- 모바일 UI 디자인 --- [cite: 2026-02-24]
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v61")

tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 정보입력", "📊 데이터관리"])

# --- 탭 1: 지도 분석 (PC급 상세 정보) --- [cite: 2026-02-24]
with tab1:
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and str(row['위도']).strip() != "":
            apt = row['아파트명']
            # 시세/호가 필터링 [cite: 2026-02-24]
            h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == apt]
            s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == apt]
            
            min_h = f"{h_df['현재호가(억)'].min():.1f}억" if not h_df.empty else "미등록"
            last_s = f"{s_df.sort_values('실거래일자').iloc[-1]['실거래가(억)']:.1f}억" if not s_df.empty else "미등록"
            phone = row['부동산전화번호'] if row['부동산전화번호'] else "번호없음"
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(str(apt))}"
            
            popup_html = f"""
            <div style='width:160px; font-size:13px;'>
                <b>🏠 {apt}</b><hr style='margin:5px 0;'>
                호가: <span style='color:red;'>{min_h}</span> / 실거래: {last_s}<br>
                📞 <a href='tel:{phone}'>{phone}</a><br>
                <a href='{n_link}' target='_blank' style='color:green; font-weight:bold;'>[N] 네이버보기</a>
            </div>
            """
            folium.Marker(
                [float(row['위도']), float(row['경도'])],
                popup=folium.Popup(popup_html, max_width=250),
                icon=folium.Icon(color="blue", icon="home")
            ).add_to(m)

    st_folium(m, width="100%", height=450, key="main_map")
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

# --- 탭 2: 정보 입력 (PC 기능) --- [cite: 2026-02-24]
with tab2:
    mode = st.radio("항목 선택", ["단지등록", "실거래/호가 추가"], horizontal=True)
    with st.form("mobile_input"):
        if mode == "단지등록":
            n_apt = st.text_input("아파트명")
            n_geo = st.text_input("좌표 (위도, 경도)")
            n_tel = st.text_input("부동산 번호")
            if st.form_submit_button("단지 저장"):
                lat, lon = map(float, n_geo.split(','))
                new_row = pd.DataFrame([{'표시':True, '아파트명':n_apt, '부동산전화번호':n_tel, '위도':lat, '경도':lon}])
                save_cloud_data(pd.concat([st.session_state.complex_df, new_row]), "apart")
        else:
            sel_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
            val_s = st.number_input("실거래가(억)", format="%.2f")
            val_h = st.number_input("현재호가(억)", format="%.2f")
            if st.form_submit_button("시세 저장"):
                # 실거래와 호가를 동시에 업데이트 [cite: 2026-02-24]
                if val_s > 0:
                    new_s = pd.DataFrame([{'실거래일자':str(date.today()), '아파트명':sel_apt, '실거래가(억)':val_s}])
                    save_cloud_data(pd.concat([st.session_state.sales_df, new_s]), "real")
                if val_h > 0:
                    new_h = pd.DataFrame([{'갱신일자':str(date.today()), '아파트명':sel_apt, '현재호가(억)':val_h}])
                    save_cloud_data(pd.concat([st.session_state.hoga_df, new_h]), "hoga")

# --- 탭 3: 데이터 관리 (편집기) --- [cite: 2026-02-24]
with tab3:
    target = st.selectbox("관리 대상", ["apart", "real", "hoga"])
    df_map = {"apart": st.session_state.complex_df, "real": st.session_state.sales_df, "hoga": st.session_state.hoga_df}
    edited = st.data_editor(df_map[target], use_container_width=True, num_rows="dynamic")
    if st.button("💾 변경사항 저장"):
        save_cloud_data(edited, target)
