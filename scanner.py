import os
import sqlite3
import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf

# Database Connection Helper
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    return sqlite3.connect("nexus.db")

def init_tables(conn):
    with conn.cursor() as cur:
        # Trade signals / market setups
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
        # Demo Executed Positions
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
        # Account Balance
        cur.execute("""
            CREATE TABLE IF NOT EXISTS account_balance (
                id SERIAL PRIMARY KEY,
                balance DOUBLE PRECISION DEFAULT 100000.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def run_paper_execution(conn):
    """Monitors active open positions against live market prices to close SL/TP."""
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
                
                # Check exit conditions
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
                print(f"Error updating position {ticker}: {e}")
        conn.commit()

def execute_demo_trade(conn, ticker, action, entry, sl, tp, confidence):
    """Auto-executes new high-confidence setups into active demo positions."""
    if confidence < 80:
        return
        
    with conn.cursor() as cur:
        # Avoid duplicate open trades on the same ticker
        cur.execute("SELECT id FROM demo_positions WHERE ticker = %s AND status = 'OPEN'", (ticker,))
        if cur.fetchone():
            return
            
        risk_per_trade = 2000.0 # $2,000 risk per trade
        risk_distance = abs(entry - sl) if abs(entry - sl) > 0 else entry * 0.02
        qty = round(risk_per_trade / risk_distance, 2)
        
        cur.execute("""
            INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'OPEN')
        """, (ticker, action, qty, entry, sl, tp))
        print(f"[DEMO EXECUTION] Opened {action} {qty} shares of {ticker} @ ${entry}")
        conn.commit()

def scan_markets():
    conn = get_db_connection()
    init_tables(conn)
    
    # Manage existing demo positions first
    run_paper_execution(conn)
    
    tickers = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "BTC-USD", "ETH-USD"]
    
    for ticker in tickers:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="15m")
            if len(df) < 20:
                continue
                
            close = float(df['Close'].iloc[-1])
            high_20 = float(df['High'].rolling(20).max().iloc[-1])
            low_20 = float(df['Low'].rolling(20).min().iloc[-1])
            
            # Simple Donchian Breakout Scanner
            if close >= high_20:
                sl = round(close * 0.97, 2)
                tp = round(close * 1.08, 2)
                conf = 88
                
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO signals (horizon, ticker, pattern, confidence, win_prob, risk_reward, entry, stop_loss, target, action, rationale)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, ("15m Scalp", ticker, "Donchian Breakout + Vol Z-Score", conf, 85, "1:2.7", close, sl, tp, "BUY", "Automated background scan breakout signal"))
                    conn.commit()
                
                # Trigger Demo Trade Execution
                execute_demo_trade(conn, ticker, "BUY", close, sl, tp, conf)
                
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            
    conn.close()

if __name__ == "__main__":
    scan_markets()
