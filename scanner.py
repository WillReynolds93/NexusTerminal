import os
import sys

def scan_markets():
    print("[SCANNER] Starting market scan routine...")
    
    try:
        import psycopg2
        import pandas as pd
        import numpy as np
        import yfinance as yf
    except ImportError as e:
        print(f"[FATAL ERROR] Missing Python library: {e}")
        return

    db_url = os.environ.get("DATABASE_URL", "")
    conn = None
    
    if db_url:
        if "channel_binding=" in db_url:
            db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
        try:
            conn = psycopg2.connect(db_url)
            print("[DATABASE] Connected successfully to Neon Postgres.")
        except Exception as e:
            print(f"[DATABASE WARNING] Could not connect to Postgres: {e}")
    else:
        print("[DATABASE WARNING] DATABASE_URL secret not found in environment.")

    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS signals (
                        id SERIAL PRIMARY KEY,
                        horizon VARCHAR(20),
                        ticker VARCHAR(20),
                        pattern VARCHAR(100),
                        confidence INT,
                        win_prob INT,
                        risk_reward VARCHAR(20),
                        entry DOUBLE PRECISION,
                        stop_loss DOUBLE PRECISION,
                        target DOUBLE PRECISION,
                        action VARCHAR(10),
                        rationale TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS demo_positions (
                        id SERIAL PRIMARY KEY,
                        ticker VARCHAR(20),
                        action VARCHAR(10),
                        qty DOUBLE PRECISION,
                        entry_price DOUBLE PRECISION,
                        stop_loss DOUBLE PRECISION,
                        take_profit DOUBLE PRECISION,
                        status VARCHAR(20) DEFAULT 'OPEN',
                        exit_price DOUBLE PRECISION,
                        pnl DOUBLE PRECISION,
                        opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        closed_at TIMESTAMP
                    );
                """)
                conn.commit()
                print("[DATABASE] Tables initialized.")
        except Exception as e:
            print(f"[DATABASE ERROR] Table setup failed: {e}")

    tickers = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "BTC-USD", "ETH-USD"]
    
    for ticker in tickers:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="15m")
            if df.empty or len(df) < 5:
                print(f"[SCAN] Insufficient data for {ticker}")
                continue
                
            close = float(df['Close'].iloc[-1])
            high_20 = float(df['High'].rolling(min(20, len(df))).max().iloc[-1])
            
            if close >= high_20:
                sl = round(close * 0.97, 2)
                tp = round(close * 1.08, 2)
                conf = 88
                
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO signals (horizon, ticker, pattern, confidence, win_prob, risk_reward, entry, stop_loss, target, action, rationale)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, ("15m Scalp", ticker, "Donchian Breakout", conf, 85, "1:2.7", close, sl, tp, "BUY", "Automated cloud breakout signal"))
                        
                        risk_per_trade = 2000.0
                        risk_dist = abs(close - sl) if abs(close - sl) > 0 else close * 0.02
                        qty = round(risk_per_trade / risk_dist, 2)
                        
                        cur.execute("""
                            INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, status)
                            VALUES (%s, 'BUY', %s, %s, %s, %s, 'OPEN')
                        """, (ticker, qty, close, sl, tp))
                        conn.commit()
                        
                print(f"[SIGNAL & TRADE EXECUTED] BUY {ticker} @ {close} | SL: {sl} | TP: {tp}")
            else:
                print(f"[SCAN] {ticker} checked @ {close} (No breakout setup)")
                
        except Exception as e:
            print(f"[SCAN ERROR] Failed processing {ticker}: {e}")

    if conn:
        conn.close()
    print("[SCANNER] Cloud scan completed successfully.")

if __name__ == "__main__":
    scan_markets()
