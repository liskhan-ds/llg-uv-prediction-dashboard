import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pml_data.db")

def create_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT UNIQUE,
        round_name TEXT NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        match_date TEXT NOT NULL,
        home_wuv REAL NOT NULL,
        away_wuv REAL NOT NULL,
        home_total_wuv REAL NOT NULL,
        away_total_wuv REAL NOT NULL,
        gap REAL NOT NULL,
        predicted_winner TEXT NOT NULL,
        prob_home REAL NOT NULL,
        prob_draw REAL NOT NULL,
        prob_away REAL NOT NULL,
        score_home INTEGER NOT NULL,
        score_away INTEGER NOT NULL,
        actual_score_home INTEGER,
        actual_score_away INTEGER,
        actual_winner TEXT,
        is_correct INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_name TEXT NOT NULL,
        player_name TEXT NOT NULL,
        position TEXT NOT NULL,
        rating REAL NOT NULL,
        goals_per90 REAL NOT NULL,
        player_uv REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(team_name, player_name) ON CONFLICT REPLACE
    )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_table()
    print(f"✅ pml_data.db 데이터베이스 및 테이블 생성 완료: {DB_PATH}")
