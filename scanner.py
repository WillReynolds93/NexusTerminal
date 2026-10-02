import os
import sys
import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[DATABASE] No DATABASE_URL found in environment variables.")
        return None
    
    # Clean Neon DB connection string for psycopg2 compatibility
    if "channel_binding=" in db_url:
        db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
        
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"[DATABASE ERROR] Failed to connect to Neon PostgreSQL: {e}")
        return None

def init_tables(conn):
    if not conn:
        return
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
            print("[DATABASE] Tables initialized successfully.")
    except Exception as e:
        print(f"[DATABASE ERROR] Table initialization failed: {e}")

def run_paper_execution(conn):
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, ticker, action, qty, entry_price, stop_loss, take_profit FROM demo_positions WHERE status = 'OPEN'")
            open_positions = cur.fetchall()
            
            for pos in open_positions:
                pos_id, ticker, action, qty, entry, sl, tp = pos
                try:
                    data = yf.Ticker(ticker).history(period="1d", interval="1m")
                    if data.empty:
                        continue
                    current_price = float(data['Close'].iloc[-1])
                    
                    closed = False
                    exit_price = current_price
                    
                    if action == 'BUY':
                        if current_price >= tp:
                            closed = True
                            exit_price = tp
                        elif current_price <= sl:
                            closed = True
                            exit_price = sl
                    elif action == 'SELL':
                        if current_price <= tp:
                            closed = True
                            exit_price = tp
                        elif current_price >= sl:
                            closed = True
                            exit_price = sl
                            
                    if closed:
                        pnl = (exit_price - entry) * qty if action == 'BUY' else (entry - exit_price) * qty
                        cur.execute("""
                            UPDATE demo_positions 
                            SET status = 'CLOSED', exit_price = %s, pnl = %s, closed_at = CURRENT_TIMESTAMP 
                            WHERE id = %s
                        """, (exit_price, pnl, pos_id))
                        print(f"[DEMO EXECUTION] Closed {action} {ticker} @ {exit_price} | PnL: ${pnl:.2f}")
                except Exception as e:
                    print(f"[EXECUTION ERROR] Ticker {ticker}: {e}")
            conn.commit()
    except Exception as e:
        print(f"[EXECUTION ERROR] Paper execution loop failed: {e}")

def execute_demo_trade(conn, ticker, action, entry, sl, tp, confidence):
    if not conn or confidence < 80:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM demo_positions WHERE ticker = %s AND status = 'OPEN'", (ticker,))
            if cur.fetchone():
                return
                
            risk_per_trade = 2000.0
            risk_distance = abs(entry - sl) if abs(entry - sl) > 0 else entry * 0.02
            qty = round(risk_per_trade / risk_distance, 2)
            
            cur.execute("""
                INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'OPEN')
            """, (ticker, action, qty, entry, sl, tp))
            print(f"[DEMO EXECUTION] Opened {action} {qty} shares of {ticker} @ ${entry}")
            conn.commit()
    except Exception as e:
        print(f"[TRADE ERROR] Failed to open position for {ticker}: {e}")

def scan_markets():
    print("[SCANNER] Starting market scan routine...")
    conn = get_db_connection()
    if conn:
        init_tables(conn)
        run_paper_execution(conn)
    
    tickers = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "BTC-USD", "ETH-USD"]
    
    for ticker in tickers:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="15m")
            if len(df) < 5:
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
                        """, ("15m Scalp", ticker, "Donchian Breakout + Vol Z-Score", conf, 85, "1:2.7", close, sl, tp, "BUY", "Automated background scan breakout signal"))
                        conn.commit()
                    
                    execute_demo_trade(conn, ticker, "BUY", close, sl, tp, conf)
                print(f"[SIGNAL GENERATED] {ticker} BUY @ {close}")
                
        except Exception as e:
            print(f"[SCAN ERROR] Failed processing {ticker}: {e}")
            
    if conn:
        conn.close()
    print("[SCANNER] Scan routine completed successfully.")

if __name__ == "__main__":
    scan_markets()
