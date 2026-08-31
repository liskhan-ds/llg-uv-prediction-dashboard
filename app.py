import os
import json
import sqlite3
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pml_data.db")
ROSTER_PATH = os.path.join(BASE_DIR, "rosters_2026.json")

TEAM_NAME_MAP = {
    "Real Madrid": "레알 마드리드",
    "Barcelona": "바르셀로나",
    "Atlético Madrid": "아틀레티코 마드리드",
    "Atletico Madrid": "아틀레티코 마드리드",
    "Athletic Club": "아틀레틱 빌바오",
    "Athletic Bilbao": "아틀레틱 빌바오",
    "Real Sociedad": "레알 소시에다드",
    "Villarreal": "비야레알",
    "Real Betis": "레알 베티스",
    "Sevilla": "세비야",
    "Valencia": "발렌시아",
    "Celta Vigo": "셀타 비고",
    "Osasuna": "오사수나",
    "Rayo Vallecano": "라요 바예카노",
    "Getafe": "헤타페",
    "Espanyol": "에스파뇰",
    "Alavés": "데포르티보 알라베스",
    "Alaves": "데포르티보 알라베스",
    "Elche": "엘체",
    "Levante": "레반테",
    "Deportivo": "데포르티보",
    "Málaga": "말라가",
    "Malaga": "말라가",
    "Racing Santander": "라싱 산탄데르",
}

OFFICIAL_STATS = {
    "Kylian Mbappé": (7.85, 0.85), "Vinícius Júnior": (7.80, 0.65), "Jude Bellingham": (7.75, 0.50),
    "Rodrygo": (7.45, 0.30), "Federico Valverde": (7.55, 0.20), "Thibaut Courtois": (7.45, 0.0),
    "Lamine Yamal": (7.85, 0.45), "Robert Lewandowski": (7.70, 0.70), "Pedri": (7.65, 0.25),
    "Raphinha": (7.60, 0.40), "Gavi": (7.40, 0.15), "Marc-André ter Stegen": (7.35, 0.0),
    "Antoine Griezmann": (7.70, 0.50), "Julián Alvarez": (7.60, 0.45), "Jan Oblak": (7.40, 0.0),
    "Nico Williams": (7.55, 0.35), "Iñaki Williams": (7.35, 0.30), "Unai Simón": (7.30, 0.0),
    "Takefusa Kubo": (7.45, 0.30), "Mikel Oyarzabal": (7.35, 0.35), "Álex Baena": (7.40, 0.25),
    "Isco": (7.40, 0.25), "Ayoze Pérez": (7.30, 0.35), "Youssef En-Nesyri": (7.25, 0.40),
    "Dani Olmo": (7.50, 0.30), "Aurélien Tchouaméni": (7.40, 0.10), "Eduardo Camavinga": (7.45, 0.12),
    "Alexander Sørloth": (7.35, 0.45), "Conor Gallagher": (7.30, 0.20), "Robin Le Normand": (7.35, 0.05),
}

TEAM_CONCEDED_PER_GAME = {
    "레알 마드리드": 0.85, "바르셀로나": 0.90, "아틀레티코 마드리드": 0.80, "아틀레틱 빌바오": 1.05,
    "레알 소시에다드": 1.10, "비야레알": 1.35, "레알 베티스": 1.25, "세비야": 1.35,
    "발렌시아": 1.40, "셀타 비고": 1.45, "오사수나": 1.40, "라요 바예카노": 1.45,
    "헤타페": 1.30, "에스파뇰": 1.55, "데포르티보 알라베스": 1.50, "엘체": 1.65,
    "레반테": 1.60, "데포르티보": 1.70, "말라가": 1.75, "라싱 산탄데르": 1.80,
}

TEAM_GOALS_PER_GAME = {
    "레알 마드리드": 2.3, "바르셀로나": 2.3, "아틀레티코 마드리드": 1.8, "아틀레틱 빌바오": 1.6,
    "레알 소시에다드": 1.5, "비야레알": 1.7, "레알 베티스": 1.4, "세비야": 1.3,
    "발렌시아": 1.2, "셀타 비고": 1.3, "오사수나": 1.15, "라요 바예카노": 1.10,
    "헤타페": 0.95, "에스파뇰": 1.0, "데포르티보 알라베스": 1.0, "엘체": 0.90,
    "레반테": 0.95, "데포르티보": 0.85, "말라가": 0.80, "라싱 산탄데르": 0.75,
}

LOW_POSSESSION_TEAMS = ["헤타페", "엘체", "레반테", "데포르티보", "말라가", "라싱 산탄데르"]

MATCHWEEK_ABSENCES = {
    "레알 마드리드": ["Jude Bellingham"],
    "바르셀로나": ["Gavi", "Ronald Araújo"],
    "아틀레티코 마드리드": ["Pablo Barrios"],
}

def normalize_team_name(raw_name):
    for key, val in TEAM_NAME_MAP.items():
        if key.lower() in raw_name.lower() or raw_name.lower() in key.lower():
            return val
    return raw_name

def calculate_player_uv(player_data, team_name=""):
    p_name_raw = player_data.get("name", "")
    p_name = normalize_team_name(p_name_raw) if "normalize_team_name" in globals() else p_name_raw.strip()
    
    rating = None
    goals_per90 = 0.0
    position = player_data.get("pos", "MF")
    
    matched = False
    for off_name, (off_r, off_g90) in OFFICIAL_STATS.items():
        if off_name.lower() in p_name_raw.lower() or p_name_raw.lower() in off_name.lower():
            rating = off_r
            goals_per90 = off_g90
            matched = True
            break
            
    if not matched and os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT rating, goals_per90, position FROM player_stats WHERE player_name = ? OR player_name LIKE ?", (p_name_raw, f"%{p_name_raw}%"))
            row = cursor.fetchone()
            if row:
                rating = row[0]
                goals_per90 = row[1]
                position = row[2]
            conn.close()
        except Exception:
            pass
            
    pos_clean = "GK" if position in ["G", "GK"] else ("DF" if position in ["D", "DF"] else ("MF" if position in ["M", "MF"] else "FW"))
    tgoals = TEAM_GOALS_PER_GAME.get(team_name, 1.30)
    is_low_poss = team_name in LOW_POSSESSION_TEAMS
    
    if rating is None:
        if pos_clean == "GK":
            raw_uv = 0.95
        elif pos_clean == "DF":
            raw_uv = 0.90
        elif pos_clean == "MF":
            raw_uv = 0.82 if is_low_poss else 0.88
        else: # FW
            raw_uv = 0.78 if tgoals < 1.1 else 0.85
    elif rating >= 6.65:
        if pos_clean == "GK":
            raw_uv = 1.0 + (rating - 6.65) * 0.45
        elif pos_clean == "DF":
            raw_uv = 1.0 + (rating - 6.65) * 0.40
        elif pos_clean == "MF":
            raw_uv = 1.0 + (rating - 6.65) * 0.35
            if is_low_poss:
                raw_uv -= 0.08
        else: # FW
            raw_uv = 1.0 + (rating - 6.65) * 0.35 + (goals_per90 * 0.20)
            if goals_per90 < 0.15 or tgoals < 1.1:
                fw_penalty = min(0.15, round(0.10 + (0.15 - max(goals_per90, 0.0)) * 0.33, 3))
                raw_uv -= fw_penalty
    else:
        slope = 0.80 if pos_clean == "MF" else 0.65
        raw_uv = 1.0 + (rating - 6.65) * slope + (goals_per90 * 0.20 if pos_clean == "FW" else 0.0)
        if pos_clean == "MF" and is_low_poss:
            raw_uv -= 0.08
        elif pos_clean == "FW" and (goals_per90 < 0.15 or tgoals < 1.1):
            fw_penalty = min(0.15, round(0.10 + (0.15 - max(goals_per90, 0.0)) * 0.33, 3))
            raw_uv -= fw_penalty
            
    conc = TEAM_CONCEDED_PER_GAME.get(team_name, 1.30)
    if pos_clean in ["GK", "DF"] and conc > 1.4:
        def_penalty = min(0.12, round(0.04 + (conc - 1.4) * 0.10, 3))
        raw_uv -= def_penalty
        
    return round(min(max(raw_uv, 0.4), 2.0), 3)

def get_team_roster(team_name, absentees=None):
    if not os.path.exists(ROSTER_PATH):
        return {"starters": [], "subs": []}
    with open(ROSTER_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)
        
    normalized_map = {normalize_team_name(k): v for k, v in rosters.items()}
    norm_tname = normalize_team_name(team_name)
    plist = normalized_map.get(norm_tname, [])
    
    if absentees is None:
        absentees = MATCHWEEK_ABSENCES.get(norm_tname, [])
        
    available = [p for p in plist if p.get("name") not in absentees]
    
    for p in available:
        p["calc_uv"] = calculate_player_uv(p, norm_tname)
        
    gks = sorted([p for p in available if p.get("pos") in ["G", "GK"]], key=lambda x: x["calc_uv"], reverse=True)
    dfs = sorted([p for p in available if p.get("pos") in ["D", "DF"]], key=lambda x: x["calc_uv"], reverse=True)
    mfs = sorted([p for p in available if p.get("pos") in ["M", "MF"]], key=lambda x: x["calc_uv"], reverse=True)
    fws = sorted([p for p in available if p.get("pos") in ["F", "FW"]], key=lambda x: x["calc_uv"], reverse=True)
    
    starters = gks[:1] + dfs[:4] + mfs[:3] + fws[:3]
    subs = (gks[1:2] + dfs[4:6] + mfs[3:5] + fws[3:5])[:5]
    return {"starters": starters, "subs": subs}

def calculate_wuv(team_name, absentees=None):
    roster = get_team_roster(team_name, absentees=absentees)
    starters = roster.get("starters", [])
    subs = roster.get("subs", [])
    
    st_uvs = [calculate_player_uv(p, team_name) for p in starters]
    sub_uvs = [calculate_player_uv(p, team_name) for p in subs]
    
    st_avg = sum(st_uvs) / len(st_uvs) if st_uvs else 0.95
    sub_avg = sum(sub_uvs) / len(sub_uvs) if sub_uvs else 0.85
    
    raw_wuv = (0.85 * st_avg + 0.15 * sub_avg)
    team_wuv = round(11.0 + 10.5 * (raw_wuv - 0.835), 2)
    
    pos_sums = {"GK": 0.0, "DF": 0.0, "MF": 0.0, "FW": 0.0}
    starters_detail = []
    for p in starters:
        uv = calculate_player_uv(p, team_name)
        pos = p.get("pos", "MF")
        pos_clean = "GK" if pos in ["G","GK"] else ("DF" if pos in ["D","DF"] else ("MF" if pos in ["M","MF"] else "FW"))
        pos_sums[pos_clean] += uv
        starters_detail.append({"name": p.get("name"), "pos": pos_clean, "uv": uv})
        
    st_tot_sum = sum(st_uvs)
    gk_wuv = round(team_wuv * (pos_sums["GK"] / st_tot_sum), 2) if st_tot_sum > 0 else 1.0
    df_wuv = round(team_wuv * (pos_sums["DF"] / st_tot_sum), 2) if st_tot_sum > 0 else 4.0
    mf_wuv = round(team_wuv * (pos_sums["MF"] / st_tot_sum), 2) if st_tot_sum > 0 else 3.0
    fw_wuv = round(team_wuv * (pos_sums["FW"] / st_tot_sum), 2) if st_tot_sum > 0 else 3.0
    
    return {
        "team_wuv": team_wuv,
        "st_avg": round(st_avg, 3),
        "sub_avg": round(sub_avg, 3),
        "st_sum": round(st_tot_sum, 3),
        "sub_sum": round(sum(sub_uvs), 3),
        "gk_wuv": gk_wuv,
        "df_wuv": df_wuv,
        "mf_wuv": mf_wuv,
        "fw_wuv": fw_wuv,
        "starters_detail": starters_detail
    }

# -----------------------------------------------------------------------------
# Streamlit 대시보드 UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PML AI 승부예측",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 상단 탭 네비게이션
nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([2, 2, 2, 2, 2])
with nav_col1:
    st.link_button(
        "🏀 NBA 대시보드 ↗", 
        "https://nba-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )
with nav_col2:
    st.link_button(
        "⚾ MLB 대시보드 ↗", 
        "https://mlb-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )
with nav_col3:
    st.button(
        "⚽ PML 대시보드 (현재)", 
        disabled=True,
        use_container_width=True
    )
with nav_col4:
    st.link_button(
        "🏒 NHL 대시보드 ↗", 
        "https://nhl-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )
with nav_col5:
    st.link_button(
        "🏈 NFL 대시보드 ↗", 
        "https://nfl-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )

st.divider()

st.title("⚽ PML AI 승부예측")

def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame([])
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(predictions)")
        cols = [row[1] for row in cursor.fetchall()]
        
        order_col = "id"
        df_db = pd.read_sql_query(f"SELECT * FROM predictions ORDER BY {order_col} ASC", conn)
        conn.close()
        
        if not df_db.empty:
            if "round_name" not in df_db.columns:
                df_db["round_name"] = "Round 1 (Gameweek 1)"
            if "date" not in df_db.columns and "match_date" in df_db.columns:
                df_db["date"] = df_db["match_date"]
            if "uk_date" not in df_db.columns:
                df_db["uk_date"] = df_db.get("date", df_db.get("match_date", "2026-08"))
            if "kst_date" not in df_db.columns:
                df_db["kst_date"] = df_db.get("date", df_db.get("match_date", "2026-08"))
            if "visit_team" not in df_db.columns and "away_team" in df_db.columns:
                df_db["visit_team"] = df_db["away_team"]
            if "visit_uv" not in df_db.columns and "away_wuv" in df_db.columns:
                df_db["visit_uv"] = df_db["away_wuv"]
            if "home_uv" not in df_db.columns and "home_total_wuv" in df_db.columns:
                df_db["home_uv"] = df_db["home_total_wuv"]
            if "predicted_gap" not in df_db.columns and "gap" in df_db.columns:
                df_db["predicted_gap"] = df_db["gap"]
            if "actual_winner" not in df_db.columns:
                df_db["actual_winner"] = ""
            if "is_correct" not in df_db.columns:
                df_db["is_correct"] = None
                
        return df_db
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame([])

df = load_data()

if not df.empty and "actual_winner" in df.columns:
    df["total_no"] = range(1, len(df) + 1)
    stats_df = df[df["actual_winner"].notna() & (df["actual_winner"] != "") & (~df["actual_winner"].isin(["경기 연기", "경기 취소"]))].copy()
else:
    df = pd.DataFrame(columns=[
        "total_no", "date", "uk_date", "kst_date", "round_name", "home_team", "visit_team",
        "predicted_winner", "predicted_gap", "prob_home", "prob_draw", "prob_away",
        "home_uv", "visit_uv", "actual_winner", "actual_score_home", "actual_score_away", "is_correct"
    ])
    stats_df = pd.DataFrame([])

st.header("📊 누적 예측 성적표")
total_stats = len(stats_df)
correct_total = stats_df['is_correct'].sum() if total_stats > 0 else 0

col_acc, col_track = st.columns([2, 1])

if total_stats > 0:
    total_acc = (correct_total / total_stats) * 100
    status_suffix = " (⚡ 신계, 시장 왜곡급)" if total_acc >= 55 else ""
    
    with col_acc:
        st.subheader(f"전체 완료 경기 적중률: `{total_acc:.2f}%`{status_suffix}")
        st.markdown(f"**적중 경기 수:** {int(correct_total)} / **완료 경기 수:** {total_stats} (전체 예정: {len(df)}경기)")
    
    with col_track:
        remaining = 100 - total_stats
        if remaining > 0:
            st.metric("100경기 시스템 검증까지", f"{remaining}경기 남음")
        else:
            st.metric("시스템 검증 상태", "검증 완료 (신계 등급)")
else:
    with col_acc:
        st.subheader(f"전체 예측 대상 경기: `{len(df)} 경기`")
        st.markdown(f"**예측 완료 경기:** {len(df)} 경기 (실시간 적중률 집계 중)")
    with col_track:
        st.metric("시스템 상태", "실시간 예측 진행 중")

st.markdown("---")

st.header("📈 라운드별 예측 성적표 (PML Gameweek)")

if not stats_df.empty:
    group_col = 'round_name' if 'round_name' in stats_df.columns else 'date'
    round_stats = stats_df.groupby(group_col, sort=False).agg(
        total_games=('home_team', 'count'),
        correct_games=('is_correct', 'sum')
    ).reset_index()

    round_stats['accuracy'] = (round_stats['correct_games'] / round_stats['total_games']) * 100
    
    def get_bar_color(acc):
        if acc >= 55: return '#A020F0'      # 보라 (신계)
        elif acc >= 50: return '#FF0000'    # 빨강 (초고수/AI)
        elif acc >= 45: return '#FFA500'    # 주황 (프로/고수)
        elif acc >= 38: return '#1E90FF'    # 파랑 (노력하는 일반인)
        elif acc >= 30: return '#008000'    # 녹색 (지극히 정상인)
        else: return '#808080'             # 회색 (예측 금지)

    round_stats['bar_color'] = round_stats['accuracy'].apply(get_bar_color)
    round_stats['label_text'] = round_stats.apply(
        lambda x: f"{int(x['correct_games'])}/{int(x['total_games'])}", 
        axis=1
    )

    round_stats_7d = round_stats.tail(7)

    base = alt.Chart(round_stats_7d).encode(x=alt.X(group_col, title='PML 라운드 (Gameweek)', sort=None))
    bars = base.mark_bar().encode(
        y=alt.Y('accuracy', title='적중률(%)', scale=alt.Scale(domain=[0, 110])),
        color=alt.Color('bar_color', scale=None),
        tooltip=[group_col, 'accuracy', 'total_games', 'correct_games']
    )
    text = base.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold').encode(
        y='accuracy', text='label_text'
    )
    st.altair_chart((bars + text).properties(height=320), use_container_width=True)
else:
    st.info("💡 예정 경기 예측 완료! (경기가 종료되는 대로 라운드별 실시간 적중률이 집계됩니다.)")

st.markdown("""
<div style="text-align: center; padding: 12px; background-color: #f0f2f6; border-radius: 10px; line-height: 1.6;">
    <span style="color: #A020F0;">●</span> <b>신계</b> (55%↑) &nbsp;&nbsp;
    <span style="color: #FF0000;">●</span> <b>초고수/AI</b> (50%~55%) &nbsp;&nbsp;
    <span style="color: #FFA500;">●</span> <b>프로/고수</b> (45%~50%) &nbsp;&nbsp;
    <span style="color: #1E90FF;">●</span> <b>노력하는 일반인</b> (38%~45%) &nbsp;&nbsp;
    <span style="color: #008000;">●</span> <b>지극히 정상인</b> (30%~38%) &nbsp;&nbsp;
    <span style="color: #808080;">●</span> <b>예측 금지</b> (30%↓)
    <br><small>* 3-Way(승/무/패) 특성상 평균 46%~48% 이상부터 통계적 손익분기점(Breakeven)을 달성합니다.</small>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

st.header("📋 라운드별 경기 리포트 (10개 매치업 카드 리스트)")

def extract_round_num(text):
    import re
    m = re.search(r'Round\s*(\d+)', str(text))
    return int(m.group(1)) if m else 0

if 'round_name' in df.columns:
    unique_dates = sorted(df['round_name'].unique(), key=extract_round_num, reverse=False)
    
    pending_df = df[df['actual_winner'].isna() | (df['actual_winner'] == '')]
    default_idx = 0
    if not pending_df.empty:
        pending_rounds = sorted(pending_df['round_name'].unique(), key=extract_round_num, reverse=False)
        target_round = pending_rounds[0]
        if target_round in unique_dates:
            default_idx = unique_dates.index(target_round)
            
    selected_date = st.selectbox("확인하고 싶은 라운드를 선택하세요:", unique_dates, index=default_idx)
    filtered_df = df[df['round_name'] == selected_date].copy().reset_index(drop=True)
else:
    unique_dates = sorted(df['date'].unique(), reverse=False)
    selected_date = st.selectbox("확인하고 싶은 라운드를 선택하세요:", unique_dates, index=0)
    filtered_df = df[df['date'] == selected_date].copy().reset_index(drop=True)

if not filtered_df.empty:
    filtered_df['day_no'] = range(1, len(filtered_df) + 1)
    
    completed_in_round = filtered_df[filtered_df['actual_winner'].notna() & (filtered_df['actual_winner'] != '') & (~filtered_df['actual_winner'].isin(['경기 연기', '경기 취소', '연기됨', '취소됨']))]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("해당 라운드 총 경기 수", f"{len(filtered_df)} 경기")
    col2.metric("경기 완료 수", f"{len(completed_in_round)} 경기")
    
    if not completed_in_round.empty:
        corr_cnt = int(completed_in_round['is_correct'].sum())
        acc = (corr_cnt / len(completed_in_round)) * 100
        col3.metric("라운드 적중률", f"{acc:.1f}% ({corr_cnt}/{len(completed_in_round)})")
    else:
        col3.metric("라운드 적중률", "⏳ 진행 예정")

    display_df = pd.DataFrame()
    display_df['No.'] = filtered_df['day_no']
    display_df['경기 일시 (영국 현지)'] = filtered_df['uk_date']
    display_df['한국 시각 (KST)'] = filtered_df['kst_date']
    display_df['홈 팀'] = filtered_df.apply(lambda r: f"{r['home_team']} ({r['home_total_wuv']:.2f} WUV)" if ('home_total_wuv' in r and pd.notna(r.get('home_total_wuv'))) else (f"{r['home_team']} ({r['home_uv']:.2f} WUV)" if pd.notna(r.get('home_uv')) else r['home_team']), axis=1)
    display_df['원정 팀'] = filtered_df.apply(lambda r: f"{r['visit_team']} ({r['visit_uv']:.2f} WUV)" if pd.notna(r.get('visit_uv')) else r['visit_team'], axis=1)
    display_df['예측 결과'] = filtered_df['predicted_winner']
    display_df['3-Way 확률 [홈%|무%|원정%]'] = filtered_df.apply(
        lambda r: f"[{r['prob_home']:.1f}% | {r['prob_draw']:.1f}% | {r['prob_away']:.1f}%]", axis=1
    )
    display_df['예상 격차(ΔUV)'] = filtered_df['predicted_gap'].apply(lambda x: f"{x:+.2f}")
    display_df['실제 결과'] = filtered_df.apply(lambda r: f"{int(r['actual_score_home'])} : {int(r['actual_score_away'])} ({r['actual_winner']})" if (pd.notna(r.get('actual_score_home')) and pd.notna(r.get('actual_winner')) and r['actual_winner'] not in ['', '경기 연기', '경기 취소', '연기됨', '취소됨']) else (r['actual_winner'] if (pd.notna(r.get('actual_winner')) and r['actual_winner'] != '') else "대기중"), axis=1)
    
    def get_status_tag(r):
        act = r['actual_winner']
        if not act or pd.isna(act) or act == '':
            return "⏳ 경기 대기중"
        if act in ['경기 연기', '경기 취소', '연기됨', '취소됨']:
            return "🚫 연기/취소 (적중 제외)"
        return "✅ 정답" if r['is_correct'] == 1 else "❌ 오답"
        
    display_df['적중 여부'] = filtered_df.apply(get_status_tag, axis=1)

    st.dataframe(display_df, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #888888; padding-top: 20px;">
        <p>ⓒ DROPSHOT (사업자 번호: 578-81-03214)</p>
        <p>Contact us: liskhan@gmail.com</p>
    </div>
    """,
    unsafe_allow_html=True
)
