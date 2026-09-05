import os
import json
import sqlite3
import zoneinfo
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "llg_data.db")

def convert_utc_to_spain_and_kst(utc_str):
    if not utc_str:
        return 'N/A', 'N/A'
    try:
        clean_str = str(utc_str).replace('Z', '+00:00')
        dt_utc = datetime.fromisoformat(clean_str)
        
        spain_tz = zoneinfo.ZoneInfo('Europe/Madrid')
        kst_tz = zoneinfo.ZoneInfo('Asia/Seoul')
        
        dt_spain = dt_utc.astimezone(spain_tz)
        dt_kst = dt_utc.astimezone(kst_tz)
        
        spain_formatted = dt_spain.strftime('%Y-%m-%d %H:%M')
        kst_formatted = dt_kst.strftime('%Y-%m-%d %H:%M')
        
        return spain_formatted, kst_formatted
    except Exception:
        return str(utc_str)[:10], str(utc_str)[:10]

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
                
            spain_dates = []
            kst_dates = []
            for _, r in df_db.iterrows():
                s_d = r.get("spain_date")
                k_d = r.get("kst_date")
                m_d = r.get("match_date", "")
                if pd.notna(s_d) and pd.notna(k_d) and ":" in str(s_d) and ":" in str(k_d):
                    spain_dates.append(str(s_d))
                    kst_dates.append(str(k_d))
                else:
                    s_fmt, k_fmt = convert_utc_to_spain_and_kst(m_d)
                    spain_dates.append(s_fmt)
                    kst_dates.append(k_fmt)
            df_db["spain_date"] = spain_dates
            df_db["kst_date"] = kst_dates
            
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
        "total_no", "date", "spain_date", "kst_date", "round_name", "home_team", "visit_team",
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
    display_df['Match Time (Spain)'] = filtered_df['spain_date']
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
