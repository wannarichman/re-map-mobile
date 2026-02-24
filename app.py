import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정 및 모바일 최적화
st.set_page_config(page_title="부동산 v70 연동형", layout="centered")

# 구글 시트 정보
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

# 구글 시트 연결 엔진
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 세션 상태 초기화 (클릭 좌표 저장용) ---
if 'clicked_coords' not in st.session_state:
    st.session_state.clicked_coords = ""

# --- 데이터 로드 함수 (안정적인 CSV 방식) ---
def load_cloud_data(ws_name, cols):
    try:
        gid_map = {"apart": "0", "real": "1725468681", "hoga": "1366546489"}
        export_url = f"{SHEET_URL}/export?format=csv&gid={gid_map.get(ws_name, '0')}"
        df = pd.read_csv(export_url)
        if '표시' not in df.columns: df.insert(0, '표시', True)
        for c in cols:
            if c not in df.columns: df[c] = ""
        for col in ['위도', '경도', '현재호가(억)', '실거래가(억)', '호가변동', '변동액']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        return df[cols]
    except Exception as e:
        st.error(f"⚠️ {ws_name} 로드 실패")
        return pd.DataFrame(columns=cols)

# --- 데이터 저장 함수 ---
def save_cloud_data(df, ws_name):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 저장 성공!")
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
    .phone-link { color: #007AFF !important; text-decoration: none; font-weight: 500; font-size: 13px !important; margin-left: 10px; }
    .phone-row { display: flex; align-items: center; margin-bottom: 5px; min-height: 20px; }
    .phone-label { color: #999; width: 35px; font-size: 10px !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v70")
tab1, tab2, tab3 = st.tabs(["📍 지도 & 좌표", "📝 정보입력", "📊 데이터관리"])

# --- 탭 1: 지도 및 클릭 좌표 추출 ---
with tab1:
    st.info("💡 지도의 원하는 지점을 클릭하면 좌표가 자동 복사됩니다 (2탭 반영)")
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and row['위도'] != 0:
            apt = row['아파트명']
            h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == apt]
            s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == apt]
            
            color, icon = "red", "home"
            h_txt, s_txt = "미등록", "미등록"
            
            if not h_df.empty:
                min_h_row = h_df.loc[h_df['현재호가(억)'].idxmin()]
                h_val, h_diff = float(min_h_row['현재호가(억)']), float(min_h_row['호가변동'])
                if h_diff <= -1.0: color, icon = "orange", "star"
                elif abs(h_val - 12.5) <= 1.5: color = "blue"
                h_c = "red" if h_diff > 0 else "blue" if h_diff < 0 else "black"
                h_txt = f"<span style='font-size:16px; font-weight:bold;'>{h_val:.2f}억</span> <span style='font-size:11px; color:{h_c};'>({h_diff:+.2f})</span>"
                
            if not s_df.empty:
                last_s = s_df.sort_values('실거래일자').iloc[-1]
                s_val, s_diff = float(last_s['실거래가(억)']), float(last_s['변동액'])
                s_c = "red" if s_diff > 0 else "blue" if s_diff < 0 else "black"
                s_txt = f"<span style='font-size:16px; font-weight:bold;'>{s_val:.2f}억</span> <span style='font-size:11px; color:{s_c};'>({s_diff:+.2f})</span>"

            raw_phones = str(row['부동산전화번호']).replace(',', '/').split('/')
            tel_content = ""
            for p in raw_phones:
                p = p.strip()
                if not p: continue
                label = "H.P" if p.startswith("010") else "TEL"
                tel_content += f"<div class='phone-row'><span class='phone-label'>{label}</span><a href='tel:{p}' class='phone-link'>{p}</a></div>"
            
            n_link = f"https://m.land.naver.com/search/result/{urllib.parse.quote(str(apt))}"
            popup_html = f"""
            <div style='width: 200px; font-family: sans-serif;'>
                <div style='font-size: 19px !important; font-weight: bold; margin-bottom: 8px;'>🏠 {apt}</div>
                <div style='margin-bottom: 12px; padding: 6px; background: #fcfcfc; border-radius: 6px;'>{tel_content}</div>
                <div style='font-size: 11px; color: #888;'>최저호가</div>{h_txt}<br>
                <div style='font-size: 11px; color: #888; margin-top:5px;'>실거래가</div>{s_txt}<br>
                <a href='{n_link}' target='_blank' style='display:block; text-align:center; color:#03c75a; margin-top:10px; font-size:12px; font-weight:bold; text-decoration:none; border:1px solid #03c75a; border-radius:5px; padding:6px;'>네이버 매물보기 [N]</a>
            </div>"""
            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(popup_html, max_width=250), icon=folium.Icon(color=color, icon=icon)).add_to(m)

    # [핵심] 지도 클릭 이벤트 캡처
    map_data = st_folium(m, width="100%", height=500, key="main_map")
    
    if map_data and map_data.get("last_clicked"):
        lat, lng = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
        st.session_state.clicked_coords = f"{lat:.6f}, {lng:.6f}"
        st.success(f"📍 좌표 선택됨: {st.session_state.clicked_coords}")
        st.toast("정보입력 탭으로 가서 등록하세요!")

# --- 탭 2: 정보 입력 (좌표 자동 반영) ---
with tab2:
    mode = st.radio("입력 종류", ["단지등록", "실거래추가", "호가추가"], horizontal=True)
    with st.form("input_v70"):
        if mode == "단지등록":
            f_name = st.text_input("아파트명")
            # [핵심] 지도에서 선택한 좌표가 자동으로 들어옴
            f_coords = st.text_input("좌표 (위도, 경도)", value=st.session_state.clicked_coords)
            f_phone = st.text_input("전화번호")
            if st.form_submit_button("단지 저장"):
                if f_coords:
                    lat, lon = map(float, f_coords.split(','))
                    new_c = pd.DataFrame([{'표시':True, '아파트명':f_name, '부동산전화번호':f_phone, '위도':lat, '경도':lon}])
                    save_cloud_data(pd.concat([st.session_state.complex_df, new_c]), "apart")
                    st.session_state.clicked_coords = "" # 저장 후 비우기
                else: st.warning("지도를 클릭해 좌표를 먼저 따주세요.")
        elif mode == "실거래추가":
            f_apt = st.selectbox("아파트", st.session_state.complex_df['아파트명'].unique())
            f_price = st.number_input("가액(억)", format="%.2f")
            f_diff = st.number_input("변동(억)", format="%.2f")
            if st.form_submit_button("실거래 저장"):
                new_s = pd.DataFrame([{'실거래일자':str(date.today()), '아파트명':f_apt, '실거래가(억)':f_price, '변동액':f_diff}])
                save_cloud_data(pd.concat([st.session_state.sales_df, new_s]), "real")
        elif mode == "호가추가":
            f_apt = st.selectbox("아파트", st.session_state.complex_df['아파트명'].unique())
            f_hoga = st.number_input("호가(억)", format="%.2f")
            f_hdiff = st.number_input("호가변동(억)", format="%.2f")
            if st.form_submit_button("호가 저장"):
                new_h = pd.DataFrame([{'갱신일자':str(date.today()), '아파트명':f_apt, '현재호가(억)':f_hoga, '호가변동':f_hdiff}])
                save_cloud_data(pd.concat([st.session_state.hoga_df, new_h]), "hoga")

# --- 탭 3: 데이터 관리 ---
with tab3:
    target = st.selectbox("편집할 탭", ["apart", "real", "hoga"])
    df_dict = {"apart": st.session_state.complex_df, "real": st.session_state.sales_df, "hoga": st.session_state.hoga_df}
    edited_df = st.data_editor(df_dict[target], use_container_width=True, num_rows="dynamic")
    if st.button("💾 데이터 일괄 저장"):
        save_cloud_data(edited_df, target)
