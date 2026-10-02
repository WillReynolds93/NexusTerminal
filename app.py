import os
import sys
import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf

# --- DATABASE CONNECTION & MIGRATION ---
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[DATABASE] No DATABASE_URL found.")
        return None
    if "channel_binding=" in db_url:
        db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        print(f"[DATABASE ERROR] Connection failed: {e}")
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
                    strategy VARCHAR(50) DEFAULT 'Donchian Breakout',
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
                    strategy VARCHAR(50) DEFAULT 'Donchian Breakout',
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP
                );
            """)
            # Migration checks for existing databases
            cur.execute("ALTER TABLE signals ADD COLUMN IF NOT EXISTS strategy VARCHAR(50) DEFAULT 'Donchian Breakout';")
            cur.execute("ALTER TABLE demo_positions ADD COLUMN IF NOT EXISTS strategy VARCHAR(50) DEFAULT 'Donchian Breakout';")
            conn.commit()
            print("[DATABASE] Tables and migrations verified.")
    except Exception as e:
        print(f"[DATABASE ERROR] Initialization failed: {e}")

# --- LEARNING & FEEDBACK ENGINE ---
def get_strategy_performance_multipliers(conn):
    """
    Queries past trade history from Neon DB and calculates
    dynamic expectancy multipliers per strategy.
    """
    default_multipliers = {
        "Donchian Breakout": 1.0,
        "Williams %R Exhaustion": 1.0,
        "Supertrend Trend Follower": 1.0
    }
    if not conn:
        return default_multipliers

    try:
        query = "SELECT strategy, pnl FROM demo_positions WHERE status = 'CLOSED' AND pnl IS NOT NULL;"
        df = pd.read_sql(query, conn)
        if df.empty:
            print("[ADAPTIVE BRAIN] No closed trade history yet. Using baseline 1.0x weights.")
            return default_multipliers

        multipliers = {}
        for strat in default_multipliers.keys():
            strat_trades = df[df['strategy'] == strat]
            if len(strat_trades) < 3:
                multipliers[strat] = 1.0
                continue
            
            wins = strat_trades[strat_trades['pnl'] > 0]['pnl']
            losses = strat_trades[strat_trades['pnl'] <= 0]['pnl'].abs()
            
            win_rate = len(wins) / len(strat_trades)
            avg_win = wins.mean() if len(wins) > 0 else 0.0
            avg_loss = losses.mean() if len(losses) > 0 else 1.0
            
            # Expectancy Calculation
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
            
            if expectancy > 50:
                multipliers[strat] = 1.25  # High performing -> boost confidence & size
            elif expectancy > 0:
                multipliers[strat] = 1.10
            elif expectancy < -50:
                multipliers[strat] = 0.50  # Underperforming -> penalize
            else:
                multipliers[strat] = 0.85
                
            print(f"[ADAPTIVE BRAIN] Strategy '{strat}': WinRate={win_rate*100:.1f}%, Expectancy=${expectancy:.2f} -> Weight={multipliers[strat]}x")

        return multipliers
    except Exception as e:
        print(f"[ADAPTIVE BRAIN ERROR] Performance evaluation failed: {e}")
        return default_multipliers

# --- PAPER EXECUTION ENGINE ---
def run_paper_execution(conn):
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, ticker, action, qty, entry_price, stop_loss, take_profit, strategy FROM demo_positions WHERE status = 'OPEN'")
            open_positions = cur.fetchall()
            
            for pos in open_positions:
                pos_id, ticker, action, qty, entry, sl, tp, strat = pos
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
                            
                    if closed:
                        pnl = (exit_price - entry) * qty if action == 'BUY' else (entry - exit_price) * qty
                        cur.execute("""
                            UPDATE demo_positions 
                            SET status = 'CLOSED', exit_price = %s, pnl = %s, closed_at = CURRENT_TIMESTAMP 
                            WHERE id = %s
                        """, (exit_price, pnl, pos_id))
                        print(f"[EXECUTION] Closed {action} {ticker} ({strat}) @ ${exit_price:.2f} | Realized PnL: ${pnl:.2f}")
                except Exception as e:
                    print(f"[EXECUTION ERROR] Ticker {ticker}: {e}")
            conn.commit()
    except Exception as e:
        print(f"[EXECUTION ERROR] Paper execution failed: {e}")

# --- TECHNICAL INDICATOR ENGINE ---
def calculate_williams_r(df, period=14):
    highest_high = df['High'].rolling(period).max()
    lowest_low = df['Low'].rolling(period).min()
    williams_r = -100 * ((highest_high - df['Close']) / (highest_high - lowest_low))
    return williams_r

def calculate_supertrend(df, period=10, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    atr = (df['High'] - df['Low']).rolling(period).mean()
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)
    return lowerband, upperband

# --- ADAPTIVE MULTI-STRATEGY SCANNER ---
def scan_markets():
    print("[SCANNER] Starting adaptive market scan routine...")
    conn = get_db_connection()
    if conn:
        init_tables(conn)
        run_paper_execution(conn)
        
    weights = get_strategy_performance_multipliers(conn)
    tickers = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "BTC-USD", "ETH-USD"]
    
    for ticker in tickers:
        try:
            df = yf.Ticker(ticker).history(period="1mo", interval="15m")
            if len(df) < 30:
                continue
                
            close = float(df['Close'].iloc[-1])
            
            # --- STRATEGY 1: Donchian Volatility Breakout ---
            high_20 = float(df['High'].rolling(20).max().iloc[-1])
            vol_mean = df['Volume'].rolling(20).mean().iloc[-1]
            current_vol = df['Volume'].iloc[-1]
            vol_z = (current_vol - vol_mean) / (df['Volume'].rolling(20).std().iloc[-1] + 1e-6)
            
            if close >= high_20 and vol_z > 1.2:
                base_conf = 80
                strat_name = "Donchian Breakout"
                final_conf = min(99, int(base_conf * weights.get(strat_name, 1.0)))
                sl = round(close * 0.97, 2)
                tp = round(close * 1.08, 2)
                process_signal(conn, ticker, "BUY", close, sl, tp, final_conf, strat_name, f"Vol breakout (Z={vol_z:.1f})")

            # --- STRATEGY 2: Williams %R Oversold Exhaustion ---
            df['williams_r'] = calculate_williams_r(df)
            df['ema200'] = df['Close'].ewm(span=200, adjust=False).mean()
            last_wr = float(df['williams_r'].iloc[-1])
            last_ema = float(df['ema200'].iloc[-1])
            
            if last_wr < -80 and close > last_ema:
                base_conf = 82
                strat_name = "Williams %R Exhaustion"
                final_conf = min(99, int(base_conf * weights.get(strat_name, 1.0)))
                sl = round(close * 0.98, 2)
                tp = round(close * 1.05, 2)
                process_signal(conn, ticker, "BUY", close, sl, tp, final_conf, strat_name, f"Exhaustion dip near 200 EMA (%R={last_wr:.1f})")

            # --- STRATEGY 3: Supertrend Trend Follower ---
            lowerband, _ = calculate_supertrend(df)
            st_val = float(lowerband.iloc[-1])
            if close > st_val and df['Close'].iloc[-2] <= lowerband.iloc[-2]:
                base_conf = 85
                strat_name = "Supertrend Trend Follower"
                final_conf = min(99, int(base_conf * weights.get(strat_name, 1.0)))
                sl = round(close * 0.96, 2)
                tp = round(close * 1.10, 2)
                process_signal(conn, ticker, "BUY", close, sl, tp, final_conf, strat_name, "Supertrend bullish flip")

        except Exception as e:
            print(f"[SCAN ERROR] Failed processing {ticker}: {e}")
            
    if conn:
        conn.close()
    print("[SCANNER] Adaptive scan completed successfully.")

def process_signal(conn, ticker, action, entry, sl, tp, conf, strategy_name, rationale):
    if conf < 75:
        print(f"[THROTTLED] {ticker} {strategy_name} signal skipped due to low feedback weight (Conf: {conf}%)")
        return

    if conn:
        try:
            with conn.cursor() as cur:
                # Log Signal
                cur.execute("""
                    INSERT INTO signals (horizon, ticker, pattern, confidence, win_prob, risk_reward, entry, stop_loss, target, action, rationale, strategy)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, ("15m Adaptive", ticker, pattern_from_strat(strategy_name), conf, conf - 3, "1:2.5", entry, sl, tp, action, rationale, strategy_name))
                
                # Check for existing open trade
                cur.execute("SELECT id FROM demo_positions WHERE ticker = %s AND status = 'OPEN'", (ticker,))
                if not cur.fetchone():
                    # Dynamic Sizing based on Confidence Weight
                    base_risk = 2000.0 * (conf / 80.0)
                    risk_dist = abs(entry - sl) if abs(entry - sl) > 0 else entry * 0.02
                    qty = round(base_risk / risk_dist, 2)
                    
                    cur.execute("""
                        INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, status, strategy)
                        VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', %s)
                    """, (ticker, action, qty, entry, sl, tp, strategy_name))
                    print(f"[LIVE TRADE EXECUTED] {action} {qty} {ticker} via {strategy_name} (Conf: {conf}%)")
                conn.commit()
        except Exception as e:
            print(f"[SIGNAL LOG ERROR] {e}")

def pattern_from_strat(strat):
    mapping = {
        "Donchian Breakout": "Donchian + Vol Z-Score",
        "Williams %R Exhaustion": "Williams %R + 200 EMA",
        "Supertrend Trend Follower": "Supertrend Flip"
    }
    return mapping.get(strat, strat)

if __name__ == "__main__":
    scan_markets()
