import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import urllib.parse
from datetime import date

# 1. 페이지 설정
st.set_page_config(page_title="부동산 v81 Fixed", layout="centered")

# 구글 시트 연결
SHEET_ID = "1aIPGxv9w0L4yMSHi8ESn8T3gSq3tNyfk2FKeZJMuu0E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 컬럼 정의 ---
COMPLEX_COLS = ['표시', '아파트명', '세대수', '연식', '출근버스', '퇴근버스', '부동산전화번호', '위도', '경도']
SALES_COLS = ['실거래일자', '아파트명', '평형(m2)', '실거래가(억)', '변동액']
HOGA_COLS = ['갱신일자', '아파트명', '평형(m2)', '동', '층', '현재호가(억)', '호가변동']

# --- 데이터 로드 함수 ---
def load_cloud_data(ws_name, cols):
    try:
        gid_map = {"apart": "0", "real": "1725468681", "hoga": "1366546489"}
        export_url = f"{SHEET_URL}/export?format=csv&gid={gid_map.get(ws_name, '0')}"
        df = pd.read_csv(export_url)
        for c in cols:
            if c not in df.columns: df[c] = ""
        num_cols = ['위도', '경도', '현재호가(억)', '실거래가(억)', '호가변동', '변동액', '세대수', '연식']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        return df[cols].fillna("")
    except Exception:
        return pd.DataFrame(columns=cols)

# --- 세션 초기화 ---
if 'complex_df' not in st.session_state: st.session_state.complex_df = load_cloud_data("apart", COMPLEX_COLS)
if 'sales_df' not in st.session_state: st.session_state.sales_df = load_cloud_data("real", SALES_COLS)
if 'hoga_df' not in st.session_state: st.session_state.hoga_df = load_cloud_data("hoga", HOGA_COLS)
if 'clicked_coords' not in st.session_state: st.session_state.clicked_coords = ""

def save_cloud_data(df, ws_name):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=ws_name, data=df)
        st.success(f"✅ {ws_name} 저장 성공!")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ 저장 실패: {e}")

# --- UI 스타일링 ---
st.markdown("""
    <style>
    .stButton > button { width: 100%; height: 3.5rem; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: bold; }
    .phone-link { color: #007AFF !important; text-decoration: none; font-size: 11px !important; margin-left: 10px; }
    .phone-row { display: flex; align-items: center; margin-bottom: 2px; height: 14px; }
    .phone-label { color: #aaa; width: 30px; font-size: 9px !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ 수도권 자산관리 v81")
tab1, tab2, tab3 = st.tabs(["📍 지도분석", "📝 정보입력", "📊 데이터관리"])

# --- 탭 1: 지도 분석 ---
with tab1:
    m = folium.Map(location=[37.5665, 126.9780], zoom_start=11)
    for _, row in st.session_state.complex_df.iterrows():
        if pd.notnull(row['위도']) and row['위도'] != 0:
            apt = row['아파트명']
            h_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == apt]
            s_df = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == apt]
            
            color, icon, h_txt, s_txt = "red", "home", "미등록", "미등록"
            if not h_df.empty:
                min_h = h_df.loc[h_df['현재호가(억)'].idxmin()]
                h_val, h_diff = float(min_h['현재호가(억)']), float(min_h['호가변동'])
                if h_diff <= -1.0: color, icon = "orange", "star"
                elif abs(h_val - 12.5) <= 1.5: color = "blue"
                h_c = "red" if h_diff > 0 else "blue" if h_diff < 0 else "black"
                h_txt = f"<span style='font-size:16px; font-weight:bold;'>{h_val:.2f}억</span> <span style='font-size:10px; color:{h_c};'>{h_diff:+.2f}</span>"
            if not s_df.empty:
                last_s = s_df.sort_values('실거래일자').iloc[-1]
                s_val, s_diff = float(last_s['실거래가(억)']), float(last_s['변동액'])
                s_c = "red" if s_diff > 0 else "blue" if s_diff < 0 else "black"
                s_txt = f"<span style='font-size:16px; font-weight:bold;'>{s_val:.2f}억</span> <span style='font-size:10px; color:{s_c};'>({s_diff:+.2f})</span>"

            phones = str(row['부동산전화번호']).replace(',', '/').split('/')
            tel_html = "".join([f"<div class='phone-row'><span class='phone-label'>{'H.P' if p.strip().startswith('010') else 'TEL'}</span><a href='tel:{p.strip()}' class='phone-link'>{p.strip()}</a></div>" for p in phones if p.strip()])
            popup_html = f"<div style='width: 200px; font-family: sans-serif;'><div style='font-size: 19px !important; font-weight: bold;'>🏠 {apt}</div><div style='margin-bottom: 8px;'>{tel_html}</div><hr style='margin: 5px 0;'><div style='font-size: 11px; color: #888;'>최저호가</div>{h_txt}<br><div style='font-size: 11px; color: #888; margin-top:5px;'>실거래가</div>{s_txt}<br><a href='https://m.land.naver.com/search/result/{urllib.parse.quote(str(apt))}' target='_blank' style='display: block; text-align: center; color: #03c75a; margin-top: 10px; font-size: 10px; font-weight: bold; text-decoration: none; border: 1px solid #03c75a; border-radius: 4px; padding: 4px;'>네이버 매물보기 [N]</a></div>"
            folium.Marker([row['위도'], row['경도']], popup=folium.Popup(popup_html, max_width=250), icon=folium.Icon(color=color, icon=icon)).add_to(m)

    map_data = st_folium(m, width="100%", height=500, key="main_map")
    if map_data and map_data.get("last_clicked"):
        st.session_state.clicked_coords = f"{map_data['last_clicked']['lat']:.6f}, {map_data['last_clicked']['lng']:.6f}"
        st.success("📍 좌표 선택됨!")

# --- 탭 2: 정보 입력 (실시간 반응형 로직 적용) ---
with tab2:
    mode = st.radio("대분류 선택", ["단지등록", "실거래추가", "호가추가"], horizontal=True)
    
    # 폼 외부에서 입력을 받아 실시간으로 화면이 바뀌게 설정
    if mode == "단지등록":
        with st.form("form_complex"):
            f_name = st.text_input("아파트명")
            c1, c2 = st.columns(2)
            f_gen, f_year = c1.number_input("세대수", step=1), c2.number_input("연식", step=1, value=2020)
            f_coords = st.text_input("좌표", value=st.session_state.clicked_coords)
            f_phone = st.text_input("부동산전화번호")
            if st.form_submit_button("🏙️ 신규 단지 저장"):
                if f_name and f_coords:
                    lat, lon = map(float, f_coords.split(','))
                    new_row = pd.DataFrame([{'표시':True, '아파트명':f_name, '세대수':f_gen, '연식':f_year, '부동산전화번호':f_phone, '위도':lat, '경도':lon}])
                    save_cloud_data(pd.concat([st.session_state.complex_df, new_row]), "apart")

    elif mode == "실거래추가":
        with st.form("form_real"):
            f_apt = st.selectbox("단지 선택", st.session_state.complex_df['아파트명'].unique())
            f_date = st.date_input("거래일자", value=date.today())
            f_size = st.text_input("평형(m2)")
            f_price = st.number_input("거래가(억)", format="%.2f")
            if st.form_submit_button("💰 실거래 추가"):
                prev_s = st.session_state.sales_df[st.session_state.sales_df['아파트명'] == f_apt]
                last_p = prev_s.sort_values('실거래일자')['실거래가(억)'].iloc[-1] if not prev_s.empty else f_price
                new_row = pd.DataFrame([{'실거래일자':str(f_date), '아파트명':f_apt, '평형(m2)':f_size, '실거래가(억)':f_price, '변동액':f_price - last_p}])
                save_cloud_data(pd.concat([st.session_state.sales_df, new_row]), "real")

    elif mode == "호가추가":
        # [핵심 수정] 폼 외부로 꺼내어 실시간 인터랙션 보장
        h_type = st.radio("입력 방식", ["기존 매물 업데이트", "신규 매물 등록"], horizontal=True)
        f_apt = st.selectbox("아파트 선택", st.session_state.complex_df['아파트명'].unique())
        
        # 선택한 아파트 데이터만 필터링
        apt_hoga_df = st.session_state.hoga_df[st.session_state.hoga_df['아파트명'] == f_apt]
        
        f_dong, f_floor, f_size, prev_val = "", "", "", 0.0
        
        if h_type == "기존 매물 업데이트":
            if not apt_hoga_df.empty:
                item_opts = apt_hoga_df.apply(lambda x: f"{x['동']}동 {x['층']}층 ({x['평형(m2)']}m2)", axis=1).unique()
                sel_item = st.selectbox("추적할 매물 선택 (리스트)", item_opts)
                matched = apt_hoga_df[apt_hoga_df.apply(lambda x: f"{x['동']}동 {x['층']}층 ({x['평형(m2)']}m2)", axis=1) == sel_item].sort_values('갱신일자').iloc[-1]
                f_dong, f_floor, f_size = matched['동'], matched['층'], matched['평형(m2)']
                prev_val = float(matched['현재호가(억)'])
                st.info(f"📍 로드된 정보: {f_dong}동 {f_floor}층 ({f_size}m2) | 이전 호가: {prev_val}억")
            else:
                st.warning("이 단지는 기존 매물이 없습니다. '신규 매물 등록'을 사용하세요.")
        else:
            # 신규 등록 클릭 시 입력 칸이 나타남
            c1, c2, c3 = st.columns(3)
            f_dong = c1.text_input("동 입력")
            f_floor = c2.text_input("층 입력")
            f_size = c3.text_input("평형 입력")

        # 저장 버튼은 별도의 작은 폼이나 버튼으로 처리
        f_hoga = st.number_input("신규 호가(억) 입력", format="%.2f", value=prev_val if prev_val > 0 else 0.0)
        if st.button("📢 호가 데이터 시트 저장"):
            if f_dong and f_floor:
                new_row = pd.DataFrame([{'갱신일자':str(date.today()), '아파트명':f_apt, '평형(m2)':f_size, '동':f_dong, '층':f_floor, '현재호가(억)':f_hoga, '호가변동':f_hoga - prev_val}])
                save_cloud_data(pd.concat([st.session_state.hoga_df, new_row]), "hoga")
            else:
                st.error("동/층 정보를 입력하거나 선택해주세요.")

# --- 탭 3: 데이터 관리 ---
with tab3:
    target = st.selectbox("시트 관리", ["apart", "real", "hoga"])
    df_map = {"apart": st.session_state.complex_df, "real": st.session_state.sales_df, "hoga": st.session_state.hoga_df}
    edited_df = st.data_editor(df_map[target], use_container_width=True, num_rows="dynamic", key=f"ed_{target}")
    if st.button("💾 클라우드 일괄 저장"): save_cloud_data(edited_df, target)
