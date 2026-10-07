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

# =====================================================================
# INDEPENDENT STRATEGY ENGINES (EVALUATED IN PARALLEL)
# =====================================================================

def strat_01_ict_liquidity_sweep(df):
    """STRATEGY 1: ICT Liquidity Stop Run & Reclaim"""
    if len(df) < 20: return False, 0, ""
    close = float(df['Close'].iloc[-1])
    low = float(df['Low'].iloc[-1])
    recent_low = float(df['Low'].iloc[-20:-1].min())
    if low <= recent_low and close > recent_low:
        return True, 82, "ICT Liquidity Sweep (20-Period Low Reclaimed)"
    return False, 0, ""

def strat_02_donchian_breakout(df):
    """STRATEGY 2: Donchian Channel Volatility Expansion"""
    if len(df) < 20: return False, 0, ""
    close = float(df['Close'].iloc[-1])
    high_20 = float(df['High'].iloc[-20:-1].max())
    if close >= high_20:
        return True, 80, "Donchian Volatility Channel Breakout"
    return False, 0, ""

def strat_03_mean_reversion_vwap_squeeze(df):
    """STRATEGY 3: VWAP & Bollinger Oversold Exhaustion Rebound"""
    if len(df) < 20: return False, 0, ""
    close = float(df['Close'].iloc[-1])
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    std20 = df['Close'].rolling(20).std().iloc[-1]
    lower_band = sma20 - (2.0 * std20)
    
    # RSI calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-6)
    rsi = 100 - (100 / (1 + rs)).iloc[-1]
    
    if close <= lower_band or rsi < 32:
        return True, int(85 + min(10, (32 - rsi) if rsi < 32 else 5)), f"Mean-Reversion Exhaustion (RSI: {rsi:.1f})"
    return False, 0, ""

def strat_04_order_flow_cvd_surge(df):
    """STRATEGY 4: CVD Order Flow & Volume Z-Score Surge"""
    if len(df) < 20: return False, 0, ""
    vol = float(df['Volume'].iloc[-1])
    vol_mean = df['Volume'].rolling(20).mean().iloc[-1]
    vol_std = df['Volume'].rolling(20).std().iloc[-1]
    z_score = (vol - vol_mean) / (vol_std + 1e-6)
    
    close = float(df['Close'].iloc[-1])
    open_p = float(df['Open'].iloc[-1])
    
    if z_score > 1.8 and close > open_p:
        return True, min(95, int(78 + z_score * 6)), f"Order Flow CVD Surge (Z-Score: {z_score:.1f}σ)"
    return False, 0, ""

def strat_05_cross_asset_relative_strength(ticker, df):
    """STRATEGY 5: Relative Strength Matrix Alpha vs Benchmark"""
    try:
        benchmark_sym = "BTC-USD" if ("-USD" in ticker or "BTC" in ticker) else "SPY"
        bench_df = yf.Ticker(benchmark_sym).history(period="5d", interval="15m")
        if len(df) >= 10 and len(bench_df) >= 10:
            asset_ret = (df['Close'].iloc[-1] - df['Close'].iloc[-10]) / df['Close'].iloc[-10]
            bench_ret = (bench_df['Close'].iloc[-1] - bench_df['Close'].iloc[-10]) / bench_df['Close'].iloc[-10]
            rs_alpha = (asset_ret - bench_ret) * 100.0
            if rs_alpha >= 2.0:
                return True, min(92, int(80 + rs_alpha * 3)), f"Relative Strength Alpha (+{rs_alpha:.2f}% vs {benchmark_sym})"
    except Exception: pass
    return False, 0, ""

# =====================================================================
# AUXILIARY CONFLUENCE METRICS (BOOSTERS)
# =====================================================================
def evaluate_options_and_sec_flow(ticker):
    """Auxiliary institutional flow boost"""
    boost = 0
    reasons = []
    if FINNHUB_KEY and not ("-USD" in ticker or "=X" in ticker):
        try:
            clean_t = ticker.replace("NASDAQ:", "").strip()
            url = f"https://finnhub.io/api/v1/stock/insider-sentiment?symbol={clean_t}&token={FINNHUB_KEY}"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                if data and data[0].get('mspr', 0) > 0:
                    boost += 6
                    reasons.append("SEC Form 4 Net Insider Buying")
        except Exception: pass
    return boost, reasons

# =====================================================================
# ADAPTIVE MULTI-STRATEGY ENSEMBLE ENGINE
# =====================================================================
def evaluate_multi_strategy_ensemble(conn, ticker, df):
    if len(df) < 20: return False, 0, "Insufficient Data", ""
    
    close = float(df['Close'].iloc[-1])
    triggered_strats = []
    
    # 1. Evaluate all 5 strategy models in parallel
    s1_hit, s1_score, s1_msg = strat_01_ict_liquidity_sweep(df)
    if s1_hit: triggered_strats.append((s1_score, "ICT Liquidity Sweep", s1_msg))
    
    s2_hit, s2_score, s2_msg = strat_02_donchian_breakout(df)
    if s2_hit: triggered_strats.append((s2_score, "Donchian Volatility Breakout", s2_msg))
    
    s3_hit, s3_score, s3_msg = strat_03_mean_reversion_vwap_squeeze(df)
    if s3_hit: triggered_strats.append((s3_score, "Mean-Reversion Exhaustion", s3_msg))
    
    s4_hit, s4_score, s4_msg = strat_04_order_flow_cvd_surge(df)
    if s4_hit: triggered_strats.append((s4_score, "Order Flow CVD Surge", s4_msg))
    
    s5_hit, s5_score, s5_msg = strat_05_cross_asset_relative_strength(ticker, df)
    if s5_hit: triggered_strats.append((s5_score, "Cross-Asset RS Alpha", s5_msg))
    
    if not triggered_strats:
        return False, 0, "No Strategy Model Triggered", ""
        
    triggered_strats.sort(key=lambda x: x[0], reverse=True)
    primary_score, primary_name, primary_msg = triggered_strats[0]
    
    multi_strat_boost = (len(triggered_strats) - 1) * 5
    inst_boost, inst_reasons = evaluate_options_and_sec_flow(ticker)
    
    final_conf = min(99, primary_score + multi_strat_boost + inst_boost)
    
    strat_list_str = " + ".join([s[1] for s in triggered_strats])
    rationales = [primary_msg] + inst_reasons
    full_rationale = f"Ensemble Signal ({strat_list_str}) | " + " | ".join(rationales)
    
    return True, final_conf, full_rationale, primary_name

# --- ACTIVE POSITIONS MONITOR ---
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

# --- MASTER SCANNER LOOP ---
def scan_markets():
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    config = get_autopilot_config(conn)
    
    monitor_open_positions(conn)

    is_weekend = datetime.now().weekday() in [5, 6]
    crypto_universe = [
        "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", 
        "ADA-USD", "XRP-USD", "DOT-USD", "NEAR-USD", "SUI-USD", "APT-USD", 
        "SHIB-USD", "LTC-USD", "UNI-USD", "PEPE-USD", "BCH-USD", "TAO-USD",
        "RENDER-USD", "INJ-USD", "FET-USD", "SEI-USD", "TIA-USD", "STX-USD"
    ]
    equity_universe = ["NVDA", "AAPL", "MSFT", "PLTR", "AMD", "SPY", "QQQ", "TSLA", "AMZN", "META", "COIN", "MSTR"]
    
    active_universe = crypto_universe if is_weekend else (crypto_universe + equity_universe)
    print(f"\n[NEXUS QUANT {now_str}] Ensemble Engine | Regime: {'24/7 WEEKEND CRYPTO' if is_weekend else 'REGULAR MARKET'} | Universe: {len(active_universe)} Assets")

    for ticker in active_universe:
        try:
            df = yf.Ticker(ticker).history(period="5d", interval="15m")
            if len(df) < 20: continue
            
            close = float(df['Close'].iloc[-1])
            
            valid_setup, win_prob, rationale, primary_strategy = evaluate_multi_strategy_ensemble(conn, ticker, df)
            
            if valid_setup:
                sl = round(close * 0.98, 2)
                tp = round(close * 1.05, 2)
                
                process_execution(
                    conn, config, ticker=ticker, action="BUY", 
                    entry=close, sl=sl, tp=tp, win_prob=win_prob, 
                    strategy=primary_strategy, rationale=rationale
                )
        except Exception as e:
            print(f"[SCAN ERROR] {ticker}: {e}")

    if conn: conn.close()

def process_execution(conn, config, ticker, action, entry, sl, tp, win_prob, strategy, rationale):
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO signals (horizon, ticker, pattern, confidence, win_prob, risk_reward, entry, stop_loss, target, action, rationale, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, ("15m Adaptive", ticker, strategy, win_prob, win_prob - 3, "1:2.5", entry, sl, tp, action, rationale, strategy))
            
            min_conf = config.get("min_conf", 80)
            is_active = config.get("active", False)
            
            if is_active and win_prob >= min_conf:
                cur.execute("SELECT id FROM demo_positions WHERE ticker = %s AND status = 'OPEN'", (ticker,))
                if not cur.fetchone():
                    risk_dist = abs(entry - sl) if abs(entry - sl) > 0 else (entry * 0.01)
                    qty = max(1.0, round((2000.0 * (win_prob / 100.0)) / risk_dist, 2))
                    
                    cur.execute("""
                        INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, strategy, status, opened_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP);
                    """, (ticker, action, qty, entry, sl, tp, strategy))
                    print(f"🚀 [ENSEMBLE AUTOPILOT] {action} {qty} {ticker} @ ${entry:,.2f} | Strategy: {strategy} | Win Prob: {win_prob}% >= Min: {min_conf}%")
            conn.commit()
    except Exception as e:
        print(f"[EXECUTION ERROR] {e}")

# --- CONTINUOUS 24/7 BACKGROUND DAEMON LOOP ---
if __name__ == "__main__":
    print("⚡ [NEXUS QUANT] Starting 24/7 Continuous Background Market Scanner...")
    while True:
        try:
            scan_markets()
        except Exception as main_e:
            print(f"[DAEMON ERROR] {main_e}")
        time.sleep(60) # Re-scans every 60 seconds
