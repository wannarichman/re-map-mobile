import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
from datetime import date
import urllib.parse

# 1. 모바일 웹 앱 스타일 설정 [cite: 2026-02-24]
st.set_page_config(page_title="부동산 v59 Mobile", layout="centered")

# [필수] 구글 시트 주소를 입력하세요.
SHEET_URL = "사용자님의_구글_시트_공유_URL을_여기에_넣으세요"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 클라우드 데이터 로직 (v58 동일 유지) --- [cite: 2026-02-24]
def load_cloud_data(ws_name, cols):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=ws_name, ttl=0)
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = True if c == '표시' else ""
        df['표시'] = df['표시'].fillna(True).astype(bool)
        return df[cols]
    except: return pd.DataFrame(columns=cols)

def save_cloud_data(df, ws_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
    st.cache_data.clear()

# --- 데이터 구조 정의 ---
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- iOS 모바일 최적화 CSS 스타일링 --- [cite: 2026-02-24]
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-size: 16px; font-weight: bold; margin-bottom: 10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; border-radius: 10px 10px 0 0; background-color: #f0f2f6; padding: 10px; }
    div[data-testid="stExpander"] { border-radius: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- 모바일 메인 UI ---
st.title("🏙️ 수도권 자산관리 v59")

tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 신규등록", "📊 데이터관리"])

with tab1:
    # v58 범례 디자인 유지 [cite: 2026-02-11, 2026-02-24]
    st.markdown("""<div style="background-color: #f9f9f9; padding: 10px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; font-size: 12px;">
        <b>📍 예산 12.5억 기준</b><br>
        <span style="color:blue;">●</span> 갭 1.5억 내 | <span style="color:red;">●</span> 갭 초과 | <span style="color:orange;">★</span> 급매
    </div>""", unsafe_allow_html=True)
    
    # [v58] 수도권 철벽 고정 지도 [cite: 2026-02-24]
    m = folium.Map(
        location=[37.5665, 126.9780], zoom_start=11, min_zoom=10, max_bounds=True,
        min_lat=37.0, max_lat=38.3, min_lon=126.4, max_lon=127.7
    )
    m.add_child(folium.LatLngPopup())

    visible_df = st.session_state.complex_df[st.session_state.complex_df['표시'] == True]
    for _, row in visible_df.iterrows():
        if pd.notnull(row['위도']):
            apt_h = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == row['아파트명']]
            apt_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == row['아파트명']]
            color, icon, status = "gray", "home", "매물없음"
            h_txt, s_txt = "정보없음", "기록없음"
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(row['아파트명'])}"
            
            if not apt_h.empty:
                min_h = apt_h.loc[apt_h['현재호가(억)'].idxmin()]
                h_val, h_diff = min_h['현재호가(억)'], min_h['호가변동']
                hc = "red" if h_diff > 0 else "blue" if h_diff < 0 else "black"
                # v58 네이버 [N] 디자인 [cite: 2026-02-24]
                h_txt = f"<b>{h_val:.1f}억</b> (<span style='color:{hc};'>{h_diff:+.1f}</span>) <a href='{n_link}' target='_blank' style='text-decoration:none; color:white; background-color:#03c75a; padding:1px 4px; border-radius:2px; font-weight:bold;'>N</a>"
                color = "blue" if abs(h_val - 12.5) <= 1.5 else "red"
                if (apt_h['현재호가(억)'].mean() - h_val) >= 1.0: color, icon = "orange", "star"
                
                matched = apt_s[apt_s['평형(m2)'] == min_h['평형(m2)']]
                if not matched.empty:
                    ls = matched.sort_values('실거래일자').iloc[-1]
                    s_txt = f"{ls['실거래가(억)']:.1f}억 ({ls['실거래일자']})"

            popup_html = f"<div style='width:200px; font-size:13px;'><b>{row['아파트명']}</b><br>📞 {row['부동산전화번호']}<hr>최저호가: {h_txt}<br>최근실거래: {s_txt}</div>"
            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(popup_html, max_width=250), icon=folium.Icon(color=color, icon=icon)).add_to(m)

    st_folium(m, width="100%", height=450, key="mobile_map")
    if st.button("🔄 지도 새로고침"): st.rerun()

with tab2:
    st.subheader("📝 단지 신규 등록")
    with st.form("mobile_reg_form", clear_on_submit=True):
        m_apt = st.text_input("아파트명")
        m_coords = st.text_input("좌표 (지도클릭 후 복사)")
        m_phone = st.text_input("부동산 연락처")
        c1, c2 = st.columns(2)
        with c1: m_house = st.number_input("세대수", min_value=0)
        with c2: m_year = st.number_input("연식", value=2010)
        if st.form_submit_button("클라우드에 단지 등록"):
            try:
                lat_v, lon_v = map(float, m_coords.split(','))
                new_c = {'표시': True, '아파트명': m_apt, '세대수': m_house, '연식': m_year, '부동산전화번호': m_phone, '위도': lat_v, '경도': lon_v}
                st.session_state.complex_df = pd.concat([st.session_state.complex_df, pd.DataFrame([new_c])], ignore_index=True)
                save_cloud_data(st.session_state.complex_df, "apart"); st.rerun()
            except: st.error("좌표 형식을 확인해주세요.")

with tab3:
    # 모바일은 필터링 후 편집이 필수 [cite: 2026-02-24]
    target_apt = st.selectbox("관리할 단지 선택", st.session_state.complex_df['아파트명'].unique())
    
    with st.expander("📊 실거래가 기록"):
        s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == target_apt]
        ed_s = st.data_editor(s_df, use_container_width=True, num_rows="dynamic", key="m_s_edit")
        if st.button("💾 실거래 수정 저장"):
            # 전체 데이터 중 해당 단지 외 데이터와 합쳐서 저장
            other_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] != target_apt]
            save_cloud_data(pd.concat([other_s, ed_s]), "real"); st.rerun()

    with st.expander("📈 매물 호가 트래킹"):
        h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == target_apt]
        ed_h = st.data_editor(h_df, use_container_width=True, num_rows="dynamic", key="m_h_edit")
        if st.button("💾 호가 수정 저장"):
            other_h = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] != target_apt]
            save_cloud_data(pd.concat([other_h, ed_h]), "hoga"); st.rerun()