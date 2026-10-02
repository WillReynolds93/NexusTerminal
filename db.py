import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

class CloudDatabaseManager:
    @staticmethod
    def get_connection():
        db_url = os.getenv("DATABASE_URL")
        if not db_url or "username:password" in db_url:
            raise ValueError("DATABASE_URL is not configured in your .env file!")
        return psycopg2.connect(db_url)

    @staticmethod
    def initialize_tables():
        conn = CloudDatabaseManager.get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_setups (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ticker VARCHAR(20) NOT NULL,
                horizon VARCHAR(20) NOT NULL,
                pattern VARCHAR(50),
                confidence INTEGER,
                ml_prob INTEGER,
                rr_ratio VARCHAR(20),
                entry_price NUMERIC,
                stop_loss NUMERIC,
                target_price NUMERIC,
                action VARCHAR(10),
                rationale TEXT
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_history (
                id SERIAL PRIMARY KEY,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ticker VARCHAR(20) NOT NULL,
                strategy_tag VARCHAR(20),
                account_id VARCHAR(50),
                side VARCHAR(10),
                size VARCHAR(20),
                entry_price NUMERIC,
                stop_loss NUMERIC,
                target_price NUMERIC,
                status VARCHAR(30)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker VARCHAR(20) PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS wishlist_params (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                condition VARCHAR(255) NOT NULL,
                trigger_price NUMERIC,
                target_amount NUMERIC,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        
        cur.execute("SELECT COUNT(*) FROM watchlist;")
        if cur.fetchone()[0] == 0:
            for symbol in ["BTC-USD", "NVDA", "GC=F", "SPY"]:
                cur.execute("INSERT INTO watchlist (ticker) VALUES (%s) ON CONFLICT DO NOTHING;", (symbol,))
            conn.commit()

        cur.execute("SELECT COUNT(*) FROM wishlist_params;")
        if cur.fetchone()[0] == 0:
            seed_wishlist = [
                ("NVDA", "Buy when down 10% from High", 118.50, 10000.0),
                ("BTC-USD", "Accumulate under $58,000 support", 58000.00, 15000.0),
                ("GC=F", "Retest of 200-EMA support", 2580.00, 8000.0)
            ]
            for w in seed_wishlist:
                cur.execute("""
                    INSERT INTO wishlist_params (ticker, condition, trigger_price, target_amount)
                    VALUES (%s, %s, %s, %s);
                """, w)
            conn.commit()

        cur.execute("SELECT COUNT(*) FROM ai_setups;")
        if cur.fetchone()[0] == 0:
            setups = [
                ("NVDA", "15m Scalp", "Donchian Breakout + Vol Z-Score", 92, 88, "1:3.2", 128.50, 125.00, 139.70, "BUY", "Institutional accumulation volume spike + Donchian Upper Band breach."),
                ("BTC-USD", "1h Swing", "Williams %R Exhaustion", 89, 84, "1:2.8", 64280.00, 62100.00, 70384.00, "BUY", "Williams %R oversold rebound aligned with 200-SMA trend support."),
                ("GC=F", "4h Swing", "Macro Inflation Hedge Model", 85, 81, "1:2.5", 2650.00, 2610.00, 2750.00, "BUY", "DXY inverse correlation divergence + central bank reserve accumulation.")
            ]
            for s in setups:
                cur.execute("""
                    INSERT INTO ai_setups (ticker, horizon, pattern, confidence, ml_prob, rr_ratio, entry_price, stop_loss, target_price, action, rationale)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, s)
            conn.commit()

        cur.close()
        conn.close()

    @staticmethod
    def get_setups_df():
        try:
            conn = CloudDatabaseManager.get_connection()
            query = """
            SELECT 
                horizon AS "Horizon", 
                ticker AS "Ticker", 
                pattern AS "Pattern", 
                confidence AS "Confidence (%)", 
                ml_prob AS "ML Win Prob (%)", 
                rr_ratio AS "Risk:Reward", 
                entry_price AS "Entry", 
                stop_loss AS "Stop Loss", 
                target_price AS "Target", 
                action AS "Action", 
                rationale AS "Rationale" 
            FROM ai_setups 
            ORDER BY confidence DESC;
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def get_watchlist():
        try:
            conn = CloudDatabaseManager.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT ticker FROM watchlist ORDER BY added_at ASC;")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return ["BTC-USD", "NVDA", "GC=F", "SPY"]

    @staticmethod
    def add_to_watchlist(ticker):
        try:
            conn = CloudDatabaseManager.get_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO watchlist (ticker) VALUES (%s) ON CONFLICT DO NOTHING;", (ticker,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

    @staticmethod
    def remove_from_watchlist(ticker):
        try:
            conn = CloudDatabaseManager.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM watchlist WHERE ticker = %s;", (ticker,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

    @staticmethod
    def get_wishlist_df():
        try:
            conn = CloudDatabaseManager.get_connection()
            query = "SELECT id, ticker, condition, trigger_price, target_amount FROM wishlist_params ORDER BY id DESC;"
            df = pd.read_sql_query(query, conn)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def add_wishlist_param(ticker, condition, trigger_price, target_amount):
        try:
            conn = CloudDatabaseManager.get_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO wishlist_params (ticker, condition, trigger_price, target_amount)
                VALUES (%s, %s, %s, %s);
            """, (ticker, condition, trigger_price, target_amount))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

    @staticmethod
    def remove_wishlist_param(param_id):
        try:
            conn = CloudDatabaseManager.get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM wishlist_params WHERE id = %s;", (param_id,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass
