import os
import sys
import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# --- DATABASE CONNECTION & CONFIGURATION ---
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

def get_autopilot_config(conn):
    """
    Fetches autopilot active state and minimum confidence threshold from Neon Postgres.
    """
    config = {"active": False, "min_conf": 80}
    if not conn:
        return config
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key_name, key_value FROM system_config WHERE key_name IN ('autopilot_active', 'autopilot_min_conf');")
            rows = cur.fetchall()
            for k, v in rows:
                if k == 'autopilot_active':
                    config['active'] = (v == 'TRUE')
                elif k == 'autopilot_min_conf':
                    config['min_conf'] = int(v)
    except Exception as e:
        print(f"[CONFIG FETCH ERROR] {e}")
    return config

def get_strategy_multipliers(conn):
    """
    Self-learning feedback loop: Calculates dynamic performance weights per strategy from trade history.
    """
    defaults = {"Donchian Breakout": 1.0, "Williams %R Exhaustion": 1.0, "Supertrend Trend Follower": 1.0, "ICT Silver Bullet Sweep": 1.0}
    if not conn:
        return defaults
    try:
        df = pd.read_sql("SELECT strategy, pnl FROM demo_positions WHERE status = 'CLOSED' AND pnl IS NOT NULL;", conn)
        if df.empty:
            return defaults
        
        multipliers = {}
        for strat in defaults.keys():
            strat_df = df[df['strategy'] == strat]
            if len(strat_df) < 3:
                multipliers[strat] = 1.0
                continue
            wins = strat_df[strat_df['pnl'] > 0]['pnl']
            losses = strat_df[strat_df['pnl'] <= 0]['pnl'].abs()
            win_rate = len(wins) / len(strat_df)
            avg_w = wins.mean() if len(wins) > 0 else 0.0
            avg_l = losses.mean() if len(losses) > 0 else 1.0
            exp = (win_rate * avg_w) - ((1 - win_rate) * avg_l)
            
            if exp > 50: multipliers[strat] = 1.20
            elif exp > 0: multipliers[strat] = 1.08
            elif exp < -50: multipliers[strat] = 0.60
            else: multipliers[strat] = 0.85
        return multipliers
    except Exception:
        return defaults

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
                    curr_price = float(data['Close'].iloc[-1])
                    closed = False
                    exit_price = curr_price
                    
                    if action == 'BUY':
                        if curr_price >= tp: closed = True; exit_price = tp
                        elif curr_price <= sl: closed = True; exit_price = sl
                    elif action == 'SELL':
                        if curr_price <= tp: closed = True; exit_price = tp
                        elif curr_price >= sl: closed = True; exit_price = sl
                            
                    if closed:
                        pnl = (exit_price - entry) * qty if action == 'BUY' else (entry - exit_price) * qty
                        cur.execute("""
                            UPDATE demo_positions 
                            SET status = 'CLOSED', exit_price = %s, pnl = %s, closed_at = CURRENT_TIMESTAMP 
                            WHERE id = %s
                        """, (exit_price, pnl, pos_id))
                        print(f"[EXECUTION] Closed {action} {ticker} ({strat}) @ ${exit_price:.2f} | Realized PnL: ${pnl:.2f}")
                except Exception as e:
                    print(f"[POSITION EVAL ERROR] {ticker}: {e}")
            conn.commit()
    except Exception as e:
        print(f"[PAPER EXECUTION ERROR] {e}")

# --- AUTONOMOUS THINKING MARKET SCANNER ---
def scan_markets():
    print("[NEXUS QUANT BRAIN] Starting multi-market scan routine...")
    conn = get_db_connection()
    
    config = get_autopilot_config(conn)
    weights = get_strategy_multipliers(conn)
    
    # Run active paper positions check
    run_paper_execution(conn)

    is_weekend = datetime.now().weekday() in [5, 6]
    
    # Market Universe Selection: Focus on 24/7 Crypto on Weekends
    crypto_tickers = ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "DOGE-USD", "LINK-USD"]
    equity_tickers = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "SPY", "QQQ"]
    
    tickers = crypto_tickers if is_weekend else (crypto_tickers + equity_tickers)
    print(f"[MARKET SELECTION] Weekend Mode: {is_weekend} | Tickers: {len(tickers)} assets")

    for ticker in tickers:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="15m")
            if len(df) < 50:
                continue
                
            close = float(df['Close'].iloc[-1])
            high = float(df['High'].iloc[-1])
            low = float(df['Low'].iloc[-1])
            
            # --- FEATURE 1: ICT A-M-D & LIQUIDITY SWEEP EVALUATION ---
            recent_high_20 = float(df['High'].iloc[-20:-1].max())
            recent_low_20 = float(df['Low'].iloc[-20:-1].min())
            
            # --- FEATURE 2: ORDER FLOW CVD SIMULATION ---
            vol_mean = df['Volume'].rolling(20).mean().iloc[-1]
            curr_vol = df['Volume'].iloc[-1]
            vol_z = (curr_vol - vol_mean) / (df['Volume'].rolling(20).std().iloc[-1] + 1e-6)
            
            # --- FEATURE 3: INDICATOR CONFLUENCE ---
            ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])
            ema200 = float(df['Close'].ewm(span=200).mean().iloc[-1])
            
            # 🧠 STRATEGY MODEL 1: ICT MANIPULATION STOP-SWEEP (BUY SIDE)
            if low < recent_low_20 and close > recent_low_20 and vol_z > 1.0:
                base_conf = 86
                strat_name = "ICT Silver Bullet Sweep"
                conf = min(99, int(base_conf * weights.get(strat_name, 1.0)))
                sl = round(low * 0.995, 2)
                tp = round(close + (close - sl) * 2.5, 2)
                process_signal(conn, config, ticker, "BUY", close, sl, tp, conf, strat_name, f"ICT Manipulation Sweep of {recent_low_20:.2f} Liquidity + CVD Spike")

            # 🧠 STRATEGY MODEL 2: DONCHIAN VOLATILITY BREAKOUT
            elif close >= recent_high_20 and vol_z > 1.2 and close > ema200:
                base_conf = 82
                strat_name = "Donchian Breakout"
                conf = min(99, int(base_conf * weights.get(strat_name, 1.0)))
                sl = round(close * 0.97, 2)
                tp = round(close * 1.08, 2)
                process_signal(conn, config, ticker, "BUY", close, sl, tp, conf, strat_name, f"Expansion Distribution Phase (Z={vol_z:.1f})")

            # 🧠 STRATEGY MODEL 3: EMA TREND REVERSION
            elif close > ema200 and close < ema50 and vol_z > 0.8:
                base_conf = 80
                strat_name = "Williams %R Exhaustion"
                conf = min(99, int(base_conf * weights.get(strat_name, 1.0)))
                sl = round(close * 0.98, 2)
                tp = round(close * 1.05, 2)
                process_signal(conn, config, ticker, "BUY", close, sl, tp, conf, strat_name, "Institutional Accumulation near 200 EMA")

        except Exception as e:
            print(f"[SCAN ERROR] {ticker}: {e}")

    if conn:
        conn.close()
    print("[NEXUS QUANT BRAIN] Autonomous market scan finished.")

def process_signal(conn, config, ticker, action, entry, sl, tp, conf, strat_name, rationale):
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            # 1. Always log signal to 'signals' table
            cur.execute("""
                INSERT INTO signals (horizon, ticker, pattern, confidence, win_prob, risk_reward, entry, stop_loss, target, action, rationale, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ("15m Adaptive", ticker, strat_name, conf, conf - 3, "1:2.5", entry, sl, tp, action, rationale, strat_name))
            
            # 2. AUTOPILOT SLIDING SCALE CHECK
            min_conf_threshold = config.get("min_conf", 80)
            is_active = config.get("active", False)
            
            if is_active and conf >= min_conf_threshold:
                cur.execute("SELECT id FROM demo_positions WHERE ticker = %s AND status = 'OPEN'", (ticker,))
                if not cur.fetchone():
                    # Dynamic Confidence Risk Sizing
                    base_risk = 2000.0 * (conf / 100.0)
                    risk_dist = abs(entry - sl) if abs(entry - sl) > 0 else (entry * 0.02)
                    qty = max(1.0, round(base_risk / risk_dist, 2))
                    
                    cur.execute("""
                        INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, strategy, status, opened_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP)
                    """, (ticker, action, qty, entry, sl, tp, strat_name))
                    print(f"🚀 [AUTOPILOT TRADE FIRED] {action} {qty} {ticker} @ ${entry:.2f} (Conf: {conf}% >= Min: {min_conf_threshold}%)")
            else:
                if is_active:
                    print(f"[AUTOPILOT SKIPPED] {ticker} {strat_name} Conf ({conf}%) below threshold ({min_conf_threshold}%)")
                else:
                    print(f"[SIGNAL LOGGED ONLY] {ticker} {strat_name} (Conf: {conf}%) | Autopilot OFF")
            conn.commit()
    except Exception as e:
        print(f"[SIGNAL PROCESS ERROR] {e}")

if __name__ == "__main__":
    scan_markets()
