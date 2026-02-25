import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정 및 모바일 최적화
st.set_page_config(page_title="부동산 자산관리 v94", layout="centered")

# [핵심] Secrets에 등록된 서비스 계정 정보를 사용하여 구글 시트와 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 구글 시트 기본 정보
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

# --- 컬럼 정의 ---
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

# --- 데이터 로드 함수 (서비스 계정 인증 적용) ---
def load_cloud_data(ws_name, cols):
    try:
        # 인증 정보를 통해 시트 읽기 (Secrets 활용)
        df = conn.read(spreadsheet=SHEET_URL, worksheet=ws_name)
        for c in cols:
            if c not in df.columns: df[c] = ""
        
        # 숫자형 데이터 변환 및 결측치 처리
        num_cols = ['위도', '경도', '현재호가(억)', '실거래가(억)', '호가변동', '변동액', '세대수', '연식']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        return df[cols].fillna("")
    except Exception:
        return pd.DataFrame(columns=cols)

# --- 세션 상태 초기화 및 데이터 선행 로드 ---
if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)
if 'clicked_coords' not in st.session_state: st.session_state.clicked_coords = ""

# --- 데이터 저장 함수 (인증 기반 쓰기 권한 사용) ---
def save_cloud_data(df, ws_name):
    try:
        # 서비스 계정 편집자 권한으로 시트 업데이트
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 데이터가 안전하게 저장되었습니다!")
        st.cache_data.clear() # 캐시 초기화하여 변경사항 즉시 반영
        st.rerun()
    except Exception as e:
        st.error(f"❌ 저장 실패: {e}")
        st.info("💡 팁: 구글 시트 공유 설정에 서비스 계정 이메일이 '편집자'로 등록되어 있는지 확인하세요.")

# --- UI 커스텀 스타일 (사용자 요구사항 반영) ---
st.markdown("""
    <style>
    /* 버튼 및 탭 스타일 */
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    
    /* 팝업 전화번호 스타일 (요구사항: 12px, 간격 15px) */
    .phone-link { color: #007AFF !important; text-decoration: none; font-size: 12px !important; margin-left: 15px; font-weight: 500; display: inline-block; }
    .phone-row { display: flex; align-items: center; margin-bottom: 4px; min-height: 22px; }
    .phone-label { color: #999; width: 38px; font-size: 10px !important; font-weight: bold; text-align: left; }
    
    /* 변동액 텍스트 크기 */
    .diff-text { font-size: 13px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 부동산 매물 정리")
tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 정보입력", "📊 데이터관리"])

# --- 탭 1: 지도 분석 ---
with tab1:
    st.markdown("""<div style="background-color: #f9f9f9; padding: 10px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 10px; font-size: 11px;">
        <b>🎨 마커 색상 기준 (12.5억 대비)</b> | <span style="color:red;">●</span> 1.5억 초과 | <span style="color:blue;">●</span> 1.5억 이하 | <span style="color:orange;">★</span> 1억 하락(급매)
    </div>""", unsafe_allow_html=True)

    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    
    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and row['위도'] != 0:
            apt = row['아파트명']
            h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == apt]
            s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == apt]
            
            # 기본 색상 및 아이콘 설정
            color, icon, h_txt, s_txt = "red", "home", "미등록", "미등록"
            
            # 호가 정보 계산
            if not h_df.empty:
                min_h = h_df.loc[h_df['현재호가(억)'].idxmin()]
                h_val, h_diff = float(min_h['현재호가(억)']), float(min_h['호가변동'])
                if h_diff <= -1.0: color, icon = "orange", "star" # 급매 표시
                elif abs(h_val - 12.5) <= 1.5: color = "blue"
                
                h_c = "red" if h_diff > 0 else "blue" if h_diff < 0 else "black"
                h_txt = f"<span style='font-size:16px; font-weight:bold;'>{h_val:.2f}억</span> <span class='diff-text' style='color:{h_c};'>({h_diff:+.2f})</span>"
            
            # 실거래 정보 계산
            if not s_df.empty:
                last_s = s_df.sort_values('실거래일자').iloc[-1]
                s_val, s_diff = float(last_s['실거래가(억)']), float(last_s['변동액'])
                s_c = "red" if s_diff > 0 else "blue" if s_diff < 0 else "black"
                s_txt = f"<span style='font-size:16px; font-weight:bold;'>{s_val:.2f}억</span> <span class='diff-text' style='color:{s_c};'>({s_diff:+.2f})</span>"

            # 전화번호 HTML 구성
            phones = str(row['부동산전화번호']).replace(',', '/').split('/')
            tel_html = "".join([f"<div class='phone-row'><span class='phone-label'>{'H.P' if p.strip().startswith('010') else 'TEL'}</span><a href='tel:{p.strip()}' class='phone-link'>{p.strip()}</a></div>" for p in phones if p.strip()])
            
            popup_html = f"""<div style='width: 210px; font-family: sans-serif; line-height: 1.3;'>
                <div style='font-size: 19px; font-weight: bold; color: #000; margin-bottom: 8px;'>🏠 {apt}</div>
                <div style='margin-bottom: 12px; padding: 6px; background: #fcfcfc; border-radius: 6px; border: 1px solid #f0f0f0;'>{tel_html}</div>
                <hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
                <div style='margin-bottom: 8px;'><span style='font-size: 11px; color: #888;'>최저호가</span><br>{h_txt}</div>
                <div style='margin-bottom: 10px;'><span style='font-size: 11px; color: #888;'>실거래가</span><br>{s_txt}</div>
                <a href='https://m.land.naver.com/search/result/{urllib.parse.quote(str(apt))}' target='_blank' style='display: block; text-align: center; color: #03c75a; font-size: 12px; font-weight: bold; text-decoration: none; border: 1px solid #03c75a; border-radius: 5px; padding: 8px;'>네이버 매물보기 [N]</a>
            </div>"""
            
            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(popup_html, max_width=250), icon=folium.Icon(color=color, icon=icon)).add_to(m)

    # 지도 렌더링 및 클릭 좌표 획득
    map_data = st_folium(m, width="100%", height=500, key="main_map_v94")
    if map_data and map_data.get("last_clicked"):
        st.session_state.clicked_coords = f"{map_data['last_clicked']['lat']:.6f}, {map_data['last_clicked']['lng']:.6f}"
        st.success("📍 좌표 선택됨! '정보입력' 탭으로 가세요.")

# --- 탭 2: 정보 입력 (실거래가 입력 포함) ---
with tab2:
    mode = st.radio("대분류", ["단지등록", "실거래추가", "호가추가"], horizontal=True)
    
    if mode == "단지등록":
        with st.form("f_complex"):
            f_name = st.text_input("아파트명")
            c1, c2 = st.columns(2)
            f_gen, f_year = c1.number_input("세대수", step=1), c2.number_input("연식", step=1, value=2020)
            f_coords = st.text_input("좌표", value=st.session_state.clicked_coords)
            f_phone = st.text_input("부동산전화번호 (구분은 / 사용)")
            if st.form_submit_button("🏙️ 신규 단지 저장"):
                if f_name and f_coords:
                    lat, lon = map(float, f_coords.split(','))
                    new_row = pd.DataFrame([{'표시':True, '아파트명':f_name, '세대수':f_gen, '연식':f_year, '출근버스':"", '퇴근버스':"", '부동산전화번호':f_phone, '위도':lat, '경도':lon}])
                    save_cloud_data(pd.concat([st.session_state.complex_df, new_row]), "apart")

    elif mode == "실거래추가":
        with st.form("f_real"):
            f_apt = st.selectbox("단지 선택", st.session_state.complex_df['아파트명'].unique())
            f_date = st.date_input("거래일자", value=date.today())
            f_size = st.text_input("평형(m2)")
            f_price = st.number_input("거래가(억)", format="%.2f")
            if st.form_submit_button("💰 실거래 저장"):
                prev_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == f_apt]
                last_p = prev_s.sort_values('실거래일자')['실거래가(억)'].iloc[-1] if not prev_s.empty else f_price
                new_row = pd.DataFrame([{'실거래일자':str(f_date), '아파트명':f_apt, '평형(m2)':f_size, '실거래가(억)':f_price, '변동액':f_price - last_p}])
                save_cloud_data(pd.concat([st.session_state.sales_df, new_row]), "real")

    elif mode == "호가추가":
        h_type = st.radio("방식", ["기존 매물 업데이트", "신규 매물 등록"], horizontal=True)
        f_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
        apt_hoga_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == f_apt]
        f_dong, f_floor, f_size, prev_val = "", "", "", 0.0
        
        if h_type == "기존 매물 업데이트" and not apt_hoga_df.empty:
            item_opts = apt_hoga_df.apply(lambda x: f"{x['동']}동 {x['층']}층 ({x['평형(m2)']}m2)", axis=1).unique()
            sel_item = st.selectbox("추적 매물 선택", item_opts)
            matched = apt_hoga_df[apt_hoga_df.apply(lambda x: f"{x['동']}동 {x['층']}층 ({x['평형(m2)']}m2)", axis=1) == sel_item].sort_values('갱신일자').iloc[-1]
            f_dong, f_floor, f_size = matched['동'], matched['층'], matched['평형(m2)']
            prev_val = float(matched['현재호가(억)'])
            st.info(f"📍 로드 완료 | 이전가: {prev_val}억")
        else:
            c1, c2, c3 = st.columns(3)
            f_dong, f_floor, f_size = c1.text_input("동"), c2.text_input("층"), c3.text_input("평형")

        f_hoga = st.number_input("신규 호가(억)", format="%.2f", value=prev_val)
        if st.button("📢 호가 저장"):
            new_row = pd.DataFrame([{'갱신일자':str(date.today()), '아파트명':f_apt, '평형(m2)':f_size, '동':f_dong, '층':f_floor, '현재호가(억)':f_hoga, '호가변동':f_hoga - prev_val}])
            save_cloud_data(pd.concat([st.session_state.hoga_df, new_row]), "hoga")

# --- 탭 3: 데이터 관리 ---
with tab3:
    target = st.selectbox("데이터 시트", ["apart", "real", "hoga"])
    df_map = {"apart": st.session_state.complex_df, "real": st.session_state.sales_df, "hoga": st.session_state.hoga_df}
    edited_df = st.data_editor(df_map[target], use_container_width=True, num_rows="dynamic", key=f"ed_{target}")
    if st.button("💾 시트 일괄 저장"):
        save_cloud_data(edited_df, target)
