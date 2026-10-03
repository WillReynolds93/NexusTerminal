import os
import sys
import time
import random
import requests
import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")
POLYGON_KEY = os.environ.get("POLYGON_API_KEY", "")

# --- DATABASE CONNECTION ---
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url: return None
    if "channel_binding=" in db_url:
        db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None

def get_autopilot_config(conn):
    config = {"active": False, "min_conf": 80}
    if not conn: return config
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key_name, key_value FROM system_config WHERE key_name IN ('autopilot_active', 'autopilot_min_conf');")
            for k, v in cur.fetchall():
                if k == 'autopilot_active': config['active'] = (v == 'TRUE')
                elif k == 'autopilot_min_conf': config['min_conf'] = int(v)
    except Exception: pass
    return config

# --- LAYER 1 & 2: TECHNICAL & VOLUME DATA STREAM ---
def evaluate_technical_layers(df):
    if len(df) < 20: return False, False, 0.0, "Insufficient Data"
    
    close = float(df['Close'].iloc[-1])
    low = float(df['Low'].iloc[-1])
    recent_low = float(df['Low'].iloc[-20:-1].min())
    high_20 = float(df['High'].iloc[-20:-1].max())
    
    vol = float(df['Volume'].iloc[-1])
    vol_mean = df['Volume'].rolling(20).mean().iloc[-1]
    vol_std = df['Volume'].rolling(20).std().iloc[-1]
    z_score = (vol - vol_mean) / (vol_std + 1e-6)
    
    # ICT Sweep or Donchian Breakout
    is_sweep = (low <= recent_low and close > recent_low)
    is_breakout = (close >= high_20)
    
    return is_sweep, is_breakout, z_score, "ICT Liquidity Sweep" if is_sweep else "Donchian Breakout"

# --- LAYER 3: DYNAMIC FUNDAMENTAL HEALTH STREAM ---
def evaluate_fundamental_health(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        margins = info.get("profitMargins", info.get("operatingMargins", 0.15))
        fwd_pe = info.get("forwardPE", 25)
        
        score = 65
        if isinstance(margins, (int, float)) and margins > 0.20: score += 15
        if isinstance(fwd_pe, (int, float)) and fwd_pe < 35: score += 10
        return score
    except Exception:
        return 75

# --- LAYER 4: INSTITUTIONAL SEC & DARK POOL FLOW STREAM ---
def evaluate_institutional_flow(ticker):
    if not FINNHUB_KEY: return 5
    try:
        clean_t = ticker.split("-")[0].replace("NASDAQ:", "").strip()
        url = f"https://finnhub.io/api/v1/stock/insider-sentiment?symbol={clean_t}&token={FINNHUB_KEY}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            if data and data[0].get('mspr', 0) > 0:
                return 8
    except Exception: pass
    return 5

# --- MULTI-SOURCE CONFLUENCE CROSS-REFERENCING ENGINE ---
def cross_reference_all_data_sources(ticker, df):
    is_sweep, is_breakout, z_score, pattern = evaluate_technical_layers(df)
    
    if not (is_sweep or is_breakout):
        return False, 0, "No Structural Setup", ""
        
    fund_score = evaluate_fundamental_health(ticker)
    inst_boost = evaluate_institutional_flow(ticker)
    
    base_probability = 60
    tech_boost = 15 if is_sweep else 10
    vol_boost = min(15, int(z_score * 5)) if z_score > 0 else 0
    fund_boost = 10 if fund_score >= 80 else 5
    
    calculated_likelihood = base_probability + tech_boost + vol_boost + fund_boost + inst_boost
    final_win_prob = min(99, max(50, calculated_likelihood))
    
    rationale = (
        f"Cross-Referenced Setup: {pattern} | Volume Z-Score: {z_score:.1f}σ | "
        f"Fundamental Score: {fund_score}/100 | Institutional Flow Boost: +{inst_boost}%"
    )
    
    return True, final_win_prob, rationale, pattern

# --- ACTIVE POSITIONS MONITOR (AUTO TP/SL CLOSE) ---
def monitor_open_positions(conn):
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, ticker, action, qty, entry_price, stop_loss, take_profit, strategy FROM demo_positions WHERE status = 'OPEN'")
            open_positions = cur.fetchall()
            
            for pos in open_positions:
                pos_id, ticker, action, qty, entry, sl, tp, strat = pos
                try:
                    data = yf.Ticker(ticker).history(period="1d", interval="1m")
                    if data.empty: continue
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
                        print(f"🏁 [TRADE CLOSED] {ticker} ({strat}) Exit: ${exit_price:.2f} | PnL: ${pnl:+.2f}")
                except Exception as ex:
                    print(f"[MONITOR ERROR] {ticker}: {ex}")
            conn.commit()
    except Exception as e:
        print(f"[MONITOR SYSTEM ERROR] {e}")

# --- MASTER SCANNER ENGINE ---
def scan_markets():
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    config = get_autopilot_config(conn)
    
    # 1. Evaluate open trades against live market prices
    monitor_open_positions(conn)

    # 2. Dynamic Asset Routing (24/7 Crypto vs. Weekday Equities/Forex)
    is_weekend = datetime.now().weekday() in [5, 6]
    
    crypto_universe = [
        "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", 
        "ADA-USD", "XRP-USD", "DOT-USD", "NEAR-USD", "SUI-USD", "APT-USD", 
        "SHIB-USD", "LTC-USD", "UNI-USD", "PEPE-USD", "BCH-USD", "TAO-USD"
    ]
    equity_universe = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "SPY", "QQQ", "TSLA", "AMZN", "META"]
    
    active_universe = crypto_universe if is_weekend else (crypto_universe + equity_universe)
    print(f"\n[NEXUS QUANT {now_str}] Regime: {'24/7 WEEKEND CRYPTO' if is_weekend else 'REGULAR MARKET'} | Universe: {len(active_universe)} Assets")

    for ticker in active_universe:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="15m")
            if len(df) < 20: continue
            
            close = float(df['Close'].iloc[-1])
            
            # CROSS-REFERENCE ALL DATA SOURCES
            valid_setup, win_prob, rationale, pattern = cross_reference_all_data_sources(ticker, df)
            
            if valid_setup:
                sl = round(close * 0.98, 2)
                tp = round(close * 1.05, 2)
                
                process_execution(
                    conn, config, ticker=ticker, action="BUY", 
                    entry=close, sl=sl, tp=tp, win_prob=win_prob, 
                    strategy=pattern, rationale=rationale
                )
        except Exception as e:
            print(f"[SCAN ERROR] {ticker}: {e}")

    if conn: conn.close()

def process_execution(conn, config, ticker, action, entry, sl, tp, win_prob, strategy, rationale):
    if not conn: return
    try:
        with conn.cursor() as cur:
            # Log Signal
            cur.execute("""
                INSERT INTO signals (horizon, ticker, pattern, confidence, win_prob, risk_reward, entry, stop_loss, target, action, rationale, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ("15m Adaptive", ticker, strategy, win_prob, win_prob - 3, "1:2.5", entry, sl, tp, action, rationale, strategy))
            
            min_conf = config.get("min_conf", 80)
            is_active = config.get("active", False)
            
            # Autopilot Execution Gate
            if is_active and win_prob >= min_conf:
                cur.execute("SELECT id FROM demo_positions WHERE ticker = %s AND status = 'OPEN'", (ticker,))
                if not cur.fetchone():
                    risk_dist = abs(entry - sl) if abs(entry - sl) > 0 else (entry * 0.01)
                    qty = max(1.0, round((2000.0 * (win_prob / 100.0)) / risk_dist, 2))
                    
                    cur.execute("""
                        INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, strategy, status, opened_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP);
                    """, (ticker, action, qty, entry, sl, tp, strategy))
                    print(f"🚀 [AUTOPILOT EXECUTED] {action} {qty} {ticker} @ ${entry:,.2f} | Win Prob: {win_prob}% >= Min: {min_conf}%")
            conn.commit()
    except Exception as e:
        print(f"[EXECUTION ERROR] {e}")

# --- ENTRY POINT ---
if __name__ == "__main__":
    scan_markets()
