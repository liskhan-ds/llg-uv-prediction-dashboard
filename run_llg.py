import sqlite3
import requests
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from espn_stats_fetcher import get_espn_player_stats
import json
import zoneinfo
import pandas as pd
import numpy as np
from datetime import datetime

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

MATCHWEEK_ABSENCES = {}

def normalize_team_name(raw_name):
    for key, val in TEAM_NAME_MAP.items():
        if key.lower() in raw_name.lower() or raw_name.lower() in key.lower():
            return val
    return raw_name

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

def fetch_and_save_rosters():
    print("🔄 Fetching La Liga 2026-27 season rosters from ESPN API...")
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams"
    try:
        res = requests.get(teams_url, timeout=10).json()
        teams = res.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])
        
        rosters = {}
        pos_map = {'G': 'GK', 'D': 'DF', 'M': 'MF', 'F': 'FW'}
        
        for t in teams:
            ti = t.get('team', {})
            t_id = ti.get('id')
            raw_tname = ti.get('displayName', '')
            norm_tname = normalize_team_name(raw_tname)
            
            r_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/teams/{t_id}/roster"
            r_res = requests.get(r_url, timeout=10).json()
            
            players = []
            for a in r_res.get('athletes', []):
                p_name = a.get('fullName')
                pos_abbr = a.get('position', {}).get('abbreviation', 'M')
                pos_clean = pos_map.get(pos_abbr, pos_abbr)
                pos_full = a.get('position', {}).get('name', 'Midfielder')
                players.append({
                    'name': p_name,
                    'pos': pos_clean,
                    'position_name': pos_full
                })
            rosters[norm_tname] = players
            
        with open(ROSTER_PATH, "w", encoding="utf-8") as f:
            json.dump(rosters, f, ensure_ascii=False, indent=2)
            
        print(f"✅ rosters_2026.json saved successfully ({len(rosters)} teams)")
        return rosters
    except Exception as e:
        print(f"⚠️ Error fetching rosters: {e}")
        return {}

def calculate_player_uv(player_data, team_name=""):
    p_name_raw = player_data.get("name", "")
    
    rating = None
    goals_per90 = 0.0
    position = player_data.get("pos", "MF")
    
    espn_res = get_espn_player_stats(p_name_raw)
    if espn_res:
        rating, goals_per90 = espn_res
        
    pos_clean = "GK" if position in ["G", "GK"] else ("DF" if position in ["D", "DF"] else ("MF" if position in ["M", "MF"] else "FW"))
    
    if rating is None or rating == 0:
        if pos_clean == "GK":
            raw_uv = 0.95
        elif pos_clean == "DF":
            raw_uv = 0.90
        elif pos_clean == "MF":
            raw_uv = 0.88
        else:
            raw_uv = 0.85
    elif rating >= 6.88:
        if pos_clean in ["GK", "DF", "MF"]:
            raw_uv = 1.0 + (rating - 6.88) * 0.50
        else: # FW
            raw_uv = 1.0 + (rating - 6.88) * 0.50 + (goals_per90 * 0.40)
    else:
        slope = 0.80 if pos_clean == "MF" else 0.65
        raw_uv = 1.0 + (rating - 6.88) * slope + (goals_per90 * 0.40 if pos_clean == "FW" else 0.0)
        
    return round(min(max(raw_uv, 0.1), 2.5), 3)

def get_team_roster(team_name, absentees=None):
    if not os.path.exists(ROSTER_PATH):
        return {"starters": [], "subs": []}
    with open(ROSTER_PATH, "r", encoding="utf-8") as f:
        rosters = json.load(f)
        
    normalized_map = {normalize_team_name(k): v for k, v in rosters.items()}
    norm_tname = normalize_team_name(team_name)
    plist = normalized_map.get(norm_tname, [])
    
    if absentees is None:
        absentees = []
        
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
    
    st_tot_sum = sum(st_uvs)
    sub_tot_sum = sum(sub_uvs)
    raw_wuv = 0.85 * st_avg + 0.15 * sub_avg
    team_wuv = round(raw_wuv * 11.0, 3)
    
    pos_sums = {"GK": 0.0, "DF": 0.0, "MF": 0.0, "FW": 0.0}
    starters_detail = []
    for p in starters:
        uv = calculate_player_uv(p, team_name)
        pos = p.get("pos", "MF")
        pos_clean = "GK" if pos in ["G","GK"] else ("DF" if pos in ["D","DF"] else ("MF" if pos in ["M","MF"] else "FW"))
        pos_sums[pos_clean] += uv
        starters_detail.append({"name": p.get("name"), "pos": pos_clean, "uv": uv})
        
    tot_st_uv = sum(pos_sums.values()) or 1.0
    gk_wuv = round(team_wuv * (pos_sums["GK"] / tot_st_uv), 2)
    df_wuv = round(team_wuv * (pos_sums["DF"] / tot_st_uv), 2)
    mf_wuv = round(team_wuv * (pos_sums["MF"] / tot_st_uv), 2)
    fw_wuv = round(team_wuv * (pos_sums["FW"] / tot_st_uv), 2)
    
    return {
        "team_wuv": team_wuv,
        "st_avg": round(st_avg, 3),
        "sub_avg": round(sub_avg, 3),
        "st_sum": round(st_tot_sum, 3),
        "sub_sum": round(sub_tot_sum, 3),
        "gk_wuv": gk_wuv,
        "df_wuv": df_wuv,
        "mf_wuv": mf_wuv,
        "fw_wuv": fw_wuv,
        "starters_detail": starters_detail
    }

def get_match_prediction(home_team, away_team):
    h_info = calculate_wuv(home_team)
    a_info = calculate_wuv(away_team)
    
    h_total = h_info["team_wuv"] + 0.15
    a_total = a_info["team_wuv"]
    
    gap = h_total - a_total
    
    home_name = normalize_team_name(home_team)
    away_name = normalize_team_name(away_team)
    
    if abs(gap) <= 0.40:
        winner = "Draw"
        code = "DRAW"
    elif gap > 0.40:
        winner = f"{home_name} Win"
        code = "HOME"
    else:
        winner = f"{away_name} Win"
        code = "AWAY"
        
    z = gap
    lh = 1.55 * z
    la = -1.55 * z
    ld = 0.35 - 1.25 * abs(z)
    
    eh, ed, ea = np.exp(lh), np.exp(ld), np.exp(la)
    tot = eh + ed + ea
    
    p_home = round((eh / tot) * 100, 1)
    p_draw = round((ed / tot) * 100, 1)
    p_away = round((ea / tot) * 100, 1)
    
    sc_h = int(round(1.35 * (h_total / 11.0)))
    sc_a = int(round(1.35 * (a_total / 11.0)))
    
    if code == "DRAW":
        sc_h = sc_a = int(round((sc_h + sc_a) / 2.0))
    elif code == "HOME" and sc_h <= sc_a:
        sc_h = sc_a + 1
    elif code == "AWAY" and sc_a <= sc_h:
        sc_a = sc_h + 1
        
    return {
        "home_wuv": h_info,
        "away_wuv": a_info,
        "h_total": h_total,
        "a_total": a_total,
        "gap": gap,
        "winner": winner,
        "code": code,
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "sc_h": sc_h,
        "sc_a": sc_a
    }

def populate_player_stats_db(rosters):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    count = 0
    for tname, plist in rosters.items():
        norm_tname = normalize_team_name(tname)
        for p in plist:
            pname = p.get("name")
            pos = p.get("pos", "MF")
            rating = 6.88
            goals90 = 0.0
            uv = calculate_player_uv(p, norm_tname)
            cursor.execute("""
            INSERT INTO player_stats (team_name, player_name, position, rating, goals_per90, player_uv)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (norm_tname, pname, pos, rating, goals90, uv))
            count += 1
            
    conn.commit()
    conn.close()
    print(f"✅ player_stats table populated with {count} players!")

def fetch_2026_la_liga_schedule():
    print("🔄 Fetching 2026-27 La Liga schedule from ESPN API...")
    months = [
        ('20260801', '20260831'), ('20260901', '20260930'), ('20261001', '20261031'),
        ('20261101', '20261130'), ('20261201', '20261231'), ('20270101', '20270131'),
        ('20270201', '20270228'), ('20270301', '20270331'), ('20270401', '20270430'),
        ('20270501', '20270531')
    ]
    
    all_events = []
    seen_ids = set()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for start, end in months:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates={start}-{end}"
        try:
            res = requests.get(url, headers=headers, timeout=10).json()
            for e in res.get('events', []):
                if e['id'] not in seen_ids:
                    seen_ids.add(e['id'])
                    all_events.append(e)
        except Exception as err:
            print(f"⚠️ Error fetching schedule ({start}-{end}): {err}")
            
    all_events.sort(key=lambda x: x['date'])
    print(f"✅ 2026-27 schedule fetched: {len(all_events)} matches")
    return all_events

def run_pipeline(mode="all"):
    from init_llg_db import create_table
    
    create_table()
    
    rosters = fetch_and_save_rosters()
    if rosters:
        populate_player_stats_db(rosters)
        
    events = fetch_2026_la_liga_schedule()
    if not events:
        print("❌ Could not fetch schedule events.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for idx, e in enumerate(events, 1):
        round_num = ((idx - 1) // 10) + 1
        round_label = f"Round {round_num} (Gameweek {round_num})"
        mw_prefix = f"MW{round_num}"
        match_in_round = ((idx - 1) % 10) + 1
        mid = f"2026_{mw_prefix}_{match_in_round}"
        
        comp = e.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            continue
            
        home_comp = competitors[0] if competitors[0].get("homeAway") == "home" else competitors[1]
        away_comp = competitors[1] if competitors[0].get("homeAway") == "home" else competitors[0]
        
        h_team_raw = home_comp.get("team", {}).get("displayName", "")
        a_team_raw = away_comp.get("team", {}).get("displayName", "")
        
        h_team = normalize_team_name(h_team_raw)
        a_team = normalize_team_name(a_team_raw)
        
        utc_date_str = e.get("date", "")
        spain_time, kst_time = convert_utc_to_spain_and_kst(utc_date_str)
        
        status_type = e.get("status", {}).get("type", {}).get("name", "")
        is_completed = (status_type == "STATUS_FULL_TIME")
        is_cancelled = status_type in ["STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_SUSPENDED", "STATUS_ABANDONED"]
        
        act_sc_h = int(home_comp.get("score")) if (is_completed and home_comp.get("score") is not None) else None
        act_sc_a = int(away_comp.get("score")) if (is_completed and away_comp.get("score") is not None) else None
        
        if is_completed and act_sc_h is not None and act_sc_a is not None:
            if act_sc_h > act_sc_a:
                act_winner = f"{h_team} Win"
            elif act_sc_a > act_sc_h:
                act_winner = f"{a_team} Win"
            else:
                act_winner = "Draw"
        elif is_cancelled:
            act_winner = "Postponed"
        else:
            act_winner = None
            
        cursor.execute("SELECT predicted_winner FROM predictions WHERE match_id = ?", (mid,))
        existing = cursor.fetchone()
        
        if existing:
            pred_winner = existing[0]
            if mode in ["score", "all"]:
                if is_completed and act_winner is not None:
                    if (act_winner == pred_winner) or (h_team in act_winner and h_team in pred_winner) or (a_team in act_winner and a_team in pred_winner):
                        is_corr = 1
                    else:
                        is_corr = 0
                else:
                    is_corr = None
                    
                cursor.execute("""
                UPDATE predictions SET
                    spain_date = ?,
                    kst_date = ?,
                    actual_score_home = ?,
                    actual_score_away = ?,
                    actual_winner = ?,
                    is_correct = ?
                WHERE match_id = ?
                """, (spain_time, kst_time, act_sc_h, act_sc_a, act_winner, is_corr, mid))
            
            if mode in ["predict", "all"]:
                pred = get_match_prediction(h_team, a_team)
                pred_winner = pred["winner"]
                cursor.execute("""
                UPDATE predictions SET
                    home_wuv = ?, away_wuv = ?, home_total_wuv = ?, away_total_wuv = ?,
                    gap = ?, predicted_winner = ?, prob_home = ?, prob_draw = ?, prob_away = ?,
                    score_home = ?, score_away = ?
                WHERE match_id = ?
                """, (
                    pred["home_wuv"]["team_wuv"], pred["away_wuv"]["team_wuv"], pred["h_total"], pred["a_total"],
                    pred["gap"], pred_winner, pred["p_home"], pred["p_draw"], pred["p_away"],
                    pred["sc_h"], pred["sc_a"], mid
                ))
        else:
            pred = get_match_prediction(h_team, a_team)
            pred_winner = pred["winner"]
            
            if is_completed and act_winner is not None:
                if (act_winner == pred_winner) or (h_team in act_winner and h_team in pred_winner) or (a_team in act_winner and a_team in pred_winner):
                    is_corr = 1
                else:
                    is_corr = 0
            else:
                is_corr = None
                
            cursor.execute("""
            INSERT INTO predictions (
                match_id, round_name, home_team, away_team, match_date, spain_date, kst_date,
                home_wuv, away_wuv, home_total_wuv, away_total_wuv,
                gap, predicted_winner, prob_home, prob_draw, prob_away,
                score_home, score_away,
                actual_score_home, actual_score_away, actual_winner, is_correct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mid, round_label, h_team, a_team, utc_date_str, spain_time, kst_time,
                pred["home_wuv"]["team_wuv"], pred["away_wuv"]["team_wuv"], pred["h_total"], pred["a_total"],
                pred["gap"], pred_winner, pred["p_home"], pred["p_draw"], pred["p_away"],
                pred["sc_h"], pred["sc_a"],
                act_sc_h, act_sc_a, act_winner, is_corr
            ))

    conn.commit()
    conn.close()
    print("🎉 LLG 2026-27 Pipeline execution complete! llg_data.db updated with Spain & KST dates.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLG Pipeline Runner")
    parser.add_argument("--mode", choices=["predict", "score", "all"], default="all", help="Pipeline execution mode")
    args = parser.parse_args()

    print(f"🚀 Starting La Liga (LLG) 2026-27 Data Pipeline (Mode: {args.mode})...", flush=True)
    run_pipeline(mode=args.mode)
