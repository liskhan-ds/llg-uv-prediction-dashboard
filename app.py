import os
import json
import sqlite3
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "llg_data.db")
ROSTER_PATH = os.path.join(BASE_DIR, "rosters_2026.json")

# La Liga 20 teams English Name Mapping
TEAM_NAME_MAP = {
    "Real Madrid": "Real Madrid",
    "Barcelona": "Barcelona",
    "Atlético Madrid": "Atlético Madrid",
    "Atletico Madrid": "Atlético Madrid",
    "Athletic Club": "Athletic Club",
    "Athletic Bilbao": "Athletic Club",
    "Real Sociedad": "Real Sociedad",
    "Villarreal": "Villarreal",
    "Real Betis": "Real Betis",
    "Sevilla": "Sevilla",
    "Valencia": "Valencia",
    "Celta Vigo": "Celta Vigo",
    "Osasuna": "Osasuna",
    "Rayo Vallecano": "Rayo Vallecano",
    "Getafe": "Getafe",
    "Espanyol": "Espanyol",
    "Alavés": "Alavés",
    "Alaves": "Alavés",
    "Elche": "Elche",
    "Levante": "Levante",
    "Deportivo": "Deportivo",
    "Málaga": "Málaga",
    "Malaga": "Málaga",
    "Racing Santander": "Racing Santander",
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
    "Real Madrid": 0.85, "Barcelona": 0.90, "Atlético Madrid": 0.80, "Athletic Club": 1.05,
    "Real Sociedad": 1.10, "Villarreal": 1.35, "Real Betis": 1.25, "Sevilla": 1.35,
    "Valencia": 1.40, "Celta Vigo": 1.45, "Osasuna": 1.40, "Rayo Vallecano": 1.45,
    "Getafe": 1.30, "Espanyol": 1.55, "Alavés": 1.50, "Elche": 1.65,
    "Levante": 1.60, "Deportivo": 1.70, "Málaga": 1.75, "Racing Santander": 1.80,
}

TEAM_GOALS_PER_GAME = {
    "Real Madrid": 2.3, "Barcelona": 2.3, "Atlético Madrid": 1.8, "Athletic Club": 1.6,
    "Real Sociedad": 1.5, "Villarreal": 1.7, "Real Betis": 1.4, "Sevilla": 1.3,
    "Valencia": 1.2, "Celta Vigo": 1.3, "Osasuna": 1.15, "Rayo Vallecano": 1.10,
    "Getafe": 0.95, "Espanyol": 1.0, "Alavés": 1.0, "Elche": 0.90,
    "Levante": 0.95, "Deportivo": 0.85, "Málaga": 0.80, "Racing Santander": 0.75,
}

LOW_POSSESSION_TEAMS = ["Getafe", "Elche", "Levante", "Deportivo", "Málaga", "Racing Santander"]

MATCHWEEK_ABSENCES = {
    "Real Madrid": ["Jude Bellingham"],
    "Barcelona": ["Gavi", "Ronald Araújo"],
    "Atlético Madrid": ["Pablo Barrios"],
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
# Streamlit Dashboard UI
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="LLG AI Match Prediction",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Top Navigation Bar (7 Sports Leagues)
# Top Navigation Bar (7 Leagues)
nav_cols = st.columns(7)
with nav_cols[0]:
    st.link_button("🏀 NBA ↗", "https://nba-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[1]:
    st.link_button("⚾ MLB ↗", "https://mlb-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[2]:
    st.link_button("⚽ EPL ↗", "https://epl-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[3]:
    st.button("⚽ La Liga (Current)", disabled=True, use_container_width=True)
with nav_cols[4]:
    st.link_button("🏒 NHL ↗", "https://nhl-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[5]:
    st.link_button("🏈 NFL ↗", "https://nfl-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[6]:
    st.link_button("⚽ MLS ↗", "https://mls-uv-prediction.streamlit.app/", use_container_width=True)

st.divider()

st.title("⚽ LLG AI Match Prediction")

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
    stats_df = df[df["actual_winner"].notna() & (df["actual_winner"] != "") & (~df["actual_winner"].isin(["Postponed", "Cancelled"]))].copy()
else:
    df = pd.DataFrame(columns=[
        "total_no", "date", "uk_date", "kst_date", "round_name", "home_team", "visit_team",
        "predicted_winner", "predicted_gap", "prob_home", "prob_draw", "prob_away",
        "home_uv", "visit_uv", "actual_winner", "actual_score_home", "actual_score_away", "is_correct"
    ])
    stats_df = pd.DataFrame([])

st.header("📊 Cumulative Prediction Scorecard")
total_stats = len(stats_df)
correct_total = stats_df['is_correct'].sum() if total_stats > 0 else 0

col_acc, col_track = st.columns([2, 1])

if total_stats > 0:
    total_acc = (correct_total / total_stats) * 100
    status_suffix = " (⚡ God Mode, Market Distorting)" if total_acc >= 55 else ""
    
    with col_acc:
        st.subheader(f"Overall Completed Matches Accuracy: `{total_acc:.2f}%`{status_suffix}")
        st.markdown(f"**Correct Predictions:** {int(correct_total)} / **Completed Matches:** {total_stats} (Total Scheduled: {len(df)} matches)")
    
    with col_track:
        remaining = 100 - total_stats
        if remaining > 0:
            st.metric("100-Match System Validation", f"{remaining} matches left")
        else:
            st.metric("System Validation Status", "Validated (Legendary Tier)")
else:
    with col_acc:
        st.subheader(f"Total Target Matches: `{len(df)} Matches`")
        st.markdown(f"**Predictions Completed:** {len(df)} matches (Calculating real-time accuracy...)")
    with col_track:
        st.metric("System Status", "Real-time predictions active")

st.markdown("---")

st.header("📈 Prediction Scorecard by Gameweek (LLG Gameweek)")

if not stats_df.empty:
    group_col = 'round_name' if 'round_name' in stats_df.columns else 'date'
    round_stats = stats_df.groupby(group_col, sort=False).agg(
        total_games=('home_team', 'count'),
        correct_games=('is_correct', 'sum')
    ).reset_index()

    round_stats['accuracy'] = (round_stats['correct_games'] / round_stats['total_games']) * 100
    
    def get_bar_color(acc):
        if acc >= 55: return '#A020F0'      # Purple (God Mode)
        elif acc >= 50: return '#FF0000'    # Red (Master/AI)
        elif acc >= 45: return '#FFA500'    # Orange (Pro/Expert)
        elif acc >= 38: return '#1E90FF'    # Blue (Skilled Amateur)
        elif acc >= 30: return '#008000'    # Green (Average Fan)
        else: return '#808080'             # Gray (Low Accuracy)

    round_stats['bar_color'] = round_stats['accuracy'].apply(get_bar_color)
    round_stats['label_text'] = round_stats.apply(
        lambda x: f"{int(x['correct_games'])}/{int(x['total_games'])}", 
        axis=1
    )

    round_stats_7d = round_stats.tail(7)

    base = alt.Chart(round_stats_7d).encode(x=alt.X(group_col, title='LLG Gameweek', sort=None))
    bars = base.mark_bar().encode(
        y=alt.Y('accuracy', title='Accuracy (%)', scale=alt.Scale(domain=[0, 110])),
        color=alt.Color('bar_color', scale=None),
        tooltip=[group_col, 'accuracy', 'total_games', 'correct_games']
    )
    text = base.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold').encode(
        y='accuracy', text='label_text'
    )
    st.altair_chart((bars + text).properties(height=320), use_container_width=True)
else:
    st.info("💡 Scheduled matches predicted! (Real-time accuracy will update as matches complete.)")

st.markdown("""
<div style="text-align: center; padding: 12px; background-color: #f0f2f6; border-radius: 10px; line-height: 1.6;">
    <span style="color: #A020F0;">●</span> <b>God Mode</b> (55%↑) &nbsp;&nbsp;
    <span style="color: #FF0000;">●</span> <b>Master / AI</b> (50%~55%) &nbsp;&nbsp;
    <span style="color: #FFA500;">●</span> <b>Pro / Expert</b> (45%~50%) &nbsp;&nbsp;
    <span style="color: #1E90FF;">●</span> <b>Skilled Amateur</b> (38%~45%) &nbsp;&nbsp;
    <span style="color: #008000;">●</span> <b>Average Fan</b> (30%~38%) &nbsp;&nbsp;
    <span style="color: #808080;">●</span> <b>Low Accuracy</b> (30%↓)
    <br><small>* Due to 3-Way (Win/Draw/Loss) nature, statistical breakeven is achieved above ~46%-48%.</small>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

st.header("📋 Match Reports by Gameweek (10 Matchup Cards List)")

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
            
    selected_date = st.selectbox("Select Gameweek:", unique_dates, index=default_idx)
    filtered_df = df[df['round_name'] == selected_date].copy().reset_index(drop=True)
else:
    unique_dates = sorted(df['date'].unique(), reverse=False)
    selected_date = st.selectbox("Select Gameweek:", unique_dates, index=0)
    filtered_df = df[df['date'] == selected_date].copy().reset_index(drop=True)

if not filtered_df.empty:
    filtered_df['day_no'] = range(1, len(filtered_df) + 1)
    
    completed_in_round = filtered_df[filtered_df['actual_winner'].notna() & (filtered_df['actual_winner'] != '') & (~filtered_df['actual_winner'].isin(['Postponed', 'Cancelled']))]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Gameweek Total Matches", f"{len(filtered_df)} Matches")
    col2.metric("Completed Matches", f"{len(completed_in_round)} Matches")
    
    if not completed_in_round.empty:
        corr_cnt = int(completed_in_round['is_correct'].sum())
        acc = (corr_cnt / len(completed_in_round)) * 100
        col3.metric("Gameweek Accuracy", f"{acc:.1f}% ({corr_cnt}/{len(completed_in_round)})")
    else:
        col3.metric("Gameweek Accuracy", "⏳ Scheduled")

    display_df = pd.DataFrame()
    display_df['No.'] = filtered_df['day_no']
    display_df['Match Date (UK)'] = filtered_df['uk_date']
    display_df['Match Time (KST)'] = filtered_df['kst_date']
    display_df['Home Team'] = filtered_df.apply(lambda r: f"{r['home_team']} ({r['home_total_wuv']:.2f} WUV)" if ('home_total_wuv' in r and pd.notna(r.get('home_total_wuv'))) else (f"{r['home_team']} ({r['home_uv']:.2f} WUV)" if pd.notna(r.get('home_uv')) else r['home_team']), axis=1)
    display_df['Away Team'] = filtered_df.apply(lambda r: f"{r['visit_team']} ({r['visit_uv']:.2f} WUV)" if pd.notna(r.get('visit_uv')) else r['visit_team'], axis=1)
    display_df['Predicted Outcome'] = filtered_df['predicted_winner']
    display_df['3-Way Probability [Home% | Draw% | Away%]'] = filtered_df.apply(
        lambda r: f"[{r['prob_home']:.1f}% | {r['prob_draw']:.1f}% | {r['prob_away']:.1f}%]", axis=1
    )
    display_df['Predicted Gap (ΔUV)'] = filtered_df['predicted_gap'].apply(lambda x: f"{x:+.2f}")
    display_df['Actual Result'] = filtered_df.apply(lambda r: f"{int(r['actual_score_home'])} : {int(r['actual_score_away'])} ({r['actual_winner']})" if (pd.notna(r.get('actual_score_home')) and pd.notna(r.get('actual_winner')) and r['actual_winner'] not in ['', 'Postponed', 'Cancelled']) else (r['actual_winner'] if (pd.notna(r.get('actual_winner')) and r['actual_winner'] != '') else "Pending"), axis=1)
    
    def get_status_tag(r):
        act = r['actual_winner']
        if not act or pd.isna(act) or act == '':
            return "⏳ Pending"
        if act in ['Postponed', 'Cancelled']:
            return "🚫 Postponed/Cancelled"
        return "✅ Correct" if r['is_correct'] == 1 else "❌ Incorrect"
        
    display_df['Accuracy Status'] = filtered_df.apply(get_status_tag, axis=1)

    st.dataframe(display_df, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #888888; padding-top: 20px;">
        <p>ⓒ DROPSHOT (Business Registration: 578-81-03214)</p>
        <p>Contact us: liskhan@gmail.com</p>
    </div>
    """,
    unsafe_allow_html=True
)
