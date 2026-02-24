import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정 및 모바일 최적화
st.set_page_config(page_title="부동산 v62 Mobile", layout="centered")

# 구글 시트 정보
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

# 구글 시트 연결 엔진
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 데이터 로드 함수 (안정적인 CSV 방식) ---
def load_cloud_data(ws_name, cols):
    try:
        gid_map = {"apart": "0", "real": "1725468681", "hoga": "1366546489"}
        export_url = f"{SHEET_URL}/export?format=csv&gid={gid_map.get(ws_name, '0')}"
        df = pd.read_csv(export_url)
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = ""
        # 숫자형 변환 (에러 방지)
        for col in ['위도', '경도', '현재호가(억)', '실거래가(억)', '호가변동', '변동액']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 로드 실패: {e}")
        return pd.DataFrame(columns=cols)

# --- 데이터 저장 함수 ---
def save_cloud_data(df, ws_name):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 저장 성공! 새로고침합니다.")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ 저장 실패 (권한 확인): {e}")

# 데이터 로딩
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)

# --- UI 스타일링 ---
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    .phone-box { line-height: 1.6; font-family: 'Courier New', monospace; font-size: 14px; margin-top: 5px; color: #444; }
    .call-btn { display: block; background-color: #007AFF; color: white !important; text-align: center; 
                padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; margin-top: 10px; font-size: 14px; }
    .popup-title { font-size: 16px; font-weight: bold; margin-bottom: 2px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v62")
tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 정보입력", "📊 데이터관리"])

# --- 탭 1: 지도 분석 (핵심 기능) ---
with tab1:
    st.markdown("""<div style="background-color:#f8f9fa; padding:10px; border-radius:10px; font-size:12px; border:1px solid #ddd; margin-bottom:10px;">
        <b>💰 예산 12.5억 기준</b><br>
        <span style='color:blue;'>●</span> 갭 1.5억 내 | <span style='color:red;'>●</span> 초과 | <span style='color:orange;'>★</span> 급매(-1억 이상)
    </div>""", unsafe_allow_html=True)

    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and row['위도'] != 0:
            apt = row['아파트명']
            h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == apt]
            s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == apt]
            
            color, icon = "red", "home"
            h_txt, s_txt = "미등록", "미등록"
            
            # 호가 및 급매 로직
            if not h_df.empty:
                min_h_row = h_df.loc[h_df['현재호가(억)'].idxmin()]
                h_val = float(min_h_row['현재호가(억)'])
                h_diff = float(min_h_row['호가변동'])
                
                if h_diff <= -1.0: color, icon = "orange", "star"
                elif abs(h_val - 12.5) <= 1.5: color = "blue"
                
                h_c = "red" if h_diff > 0 else "blue" if h_diff < 0 else "black"
                h_txt = f"<b>{h_val:.2f}억</b> (<span style='color:{h_c};'>{h_diff:+.2f}</span>)"
                
            # 실거래가 로직
            if not s_df.empty:
                last_s = s_df.sort_values('실거래일자').iloc[-1]
                s_val = float(last_s['실거래가(억)'])
                s_diff = float(last_s['변동액'])
                s_c = "red" if s_diff > 0 else "blue" if s_diff < 0 else "black"
                s_txt = f"<b>{s_val:.2f}억</b> (<span style='color:{s_c};'>{s_diff:+.2f}</span>)"

            # 전화번호 줄바꿈 및 정렬
            phones = str(row['부동산전화번호']).replace(',', '/').split('/')
            tel_html = "<div class='phone-box'>"
            main_tel = ""
            for p in phones:
                p = p.strip()
                if p:
                    tel_html += f"📞 {p}<br>"
                    if not main_tel: main_tel = p
            tel_html += "</div>"
            
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(str(apt))}"
            popup_html = f"""
            <div style='width:210px; font-family:sans-serif;'>
                <div class='popup-title'>{apt}</div>
                {tel_html}
                <hr style='margin:8px 0;'>
                최저호가: {h_txt}<br>
                실거래가: {s_txt}<br>
                <a href='tel:{main_tel}' class='call-btn'>📞 전화걸기</a>
                <a href='{n_link}' target='_blank' style='display:block; text-align:center; color:#03c75a; margin-top:10px; font-size:12px; font-weight:bold; text-decoration:none;'>네이버 매물보기 [N]</a>
            </div>
            """
            folium.Marker([row['위도'], row['경도']], 
                          popup=folium.Popup(popup_html, max_width=250), 
                          icon=folium.Icon(color=color, icon=icon)).add_to(m)

    st_folium(m, width="100%", height=500, key="main_map")
    if st.button("🔄 전체 데이터 강제 새로고침"):
        st.cache_data.clear()
        st.rerun()

# --- 탭 2: 정보 입력 ---
with tab2:
    st.subheader("📝 신규 데이터 입력")
    mode = st.radio("입력 종류", ["단지등록", "실거래추가", "호가추가"], horizontal=True)
    
    with st.form("input_form_v62"):
        if mode == "단지등록":
            f_name = st.text_input("아파트명")
            f_coords = st.text_input("좌표 (예: 37.56, 126.97)")
            f_phone = st.text_input("부동산 전화번호 (여러개는 / 로 구분)")
            if st.form_submit_button("단지 저장"):
                lat, lon = map(float, f_coords.split(','))
                new_c = pd.DataFrame([{'표시':True, '아파트명':f_name, '부동산전화번호':f_phone, '위도':lat, '경도':lon}])
                save_cloud_data(pd.concat([st.session_state.complex_df, new_c]), "apart")
        
        elif mode == "실거래추가":
            f_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
            f_date = st.date_input("거래일자", date.today())
            f_price = st.number_input("실거래가(억)", format="%.2f")
            f_diff = st.number_input("변동액(억)", format="%.2f")
            if st.form_submit_button("실거래 저장"):
                new_s = pd.DataFrame([{'실거래일자':str(f_date), '아파트명':f_apt, '실거래가(억)':f_price, '변동액':f_diff}])
                save_cloud_data(pd.concat([st.session_state.sales_df, new_s]), "real")

        elif mode == "호가추가":
            f_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
            f_hoga = st.number_input("현재호가(억)", format="%.2f")
            f_hdiff = st.number_input("호가변동(억)", format="%.2f")
            if st.form_submit_button("호가 저장"):
                new_h = pd.DataFrame([{'갱신일자':str(date.today()), '아파트명':f_apt, '현재호가(억)':f_hoga, '호가변동':f_hdiff}])
                save_cloud_data(pd.concat([st.session_state.hoga_df, new_h]), "hoga")

# --- 탭 3: 데이터 관리 ---
with tab3:
    st.subheader("📊 데이터 편집 및 삭제")
    target = st.selectbox("편집할 탭 선택", ["apart", "real", "hoga"])
    df_dict = {"apart": st.session_state.complex_df, "real": st.session_state.sales_df, "hoga": st.session_state.hoga_df}
    
    edited_df = st.data_editor(df_dict[target], use_container_width=True, num_rows="dynamic")
    if st.button(f"{target} 변경사항 클라우드 저장"):
        save_cloud_data(edited_df, target)
