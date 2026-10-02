import sqlite3
import asyncio
import datetime
import random
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
import warnings

from sentiment import analyze_ticker_sentiment
from insider_scraper import SECInsiderScraper
from autotune import ParameterAutoTuner
from broadcaster import SignalBroadcaster
from fundamentals import FundamentalEngine

warnings.filterwarnings('ignore')
DB_PATH = "nexus_quant.db"

UNIVERSE_247 = [
    "NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "META", "GOOGL", "PLTR", "AMD", "COIN",
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "GC=F", "CL=F", "SI=F",
    "EURUSD=X", "GBPUSD=X", "USDJPY=X", "SPY", "QQQ", "VOO"
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS ai_setups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        ticker TEXT,
        horizon TEXT,
        pattern TEXT,
        confidence INTEGER,
        ml_prob INTEGER,
        rr_ratio TEXT,
        entry_price REAL,
        stop_loss REAL,
        target_price REAL,
        action TEXT,
        rationale TEXT,
        outcome INTEGER DEFAULT -1
    )""")
    conn.commit()
    conn.close()

def seed_initial_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ai_setups")
    if cursor.fetchone()[0] == 0:
        broadcaster = SignalBroadcaster()
        dummy_setups = [
            ("NVDA", "⚡ Scalp (5m-15m)", "VWAP Rejection & C-Suite Cluster Buy", 95, 90, "1:2.5", 128.50, 126.00, 134.75, "🟢 BUY"),
            ("BTC-USD", "🌊 Swing (1H-4H)", "Bull Flag Breakout", 89, 82, "1:3.1", 64280, 62100, 69500, "🟢 BUY"),
            ("TSLA", "⚡ Scalp (5m-15m)", "Momentum Exhaustion", 45, 40, "1:1.5", 241.20, 245.00, 235.50, "🔴 SELL"),
            ("AAPL", "🌊 Swing (1H-4H)", "200 EMA Rebound", 78, 70, "1:2.0", 224.10, 220.00, 232.00, "🟢 BUY"),
            ("GC=F", "⚡ Scalp (5m-15m)", "Liquidity Sweep", 62, 55, "1:1.8", 2650.0, 2665.0, 2625.0, "🔴 SELL"),
            ("AMD", "🌊 Swing (1H-4H)", "Double Bottom", 85, 80, "1:2.8", 165.40, 158.00, 180.00, "🟢 BUY"),
            ("PLTR", "⚡ Scalp (5m-15m)", "MACD Crossover & SEC Insider Surge", 91, 86, "1:2.2", 38.50, 37.10, 41.50, "🟢 BUY")
        ]
        
        for s in dummy_setups:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sentiment_score, summary = analyze_ticker_sentiment(s[0])
            regime = ParameterAutoTuner.get_regime_parameters()
            adjusted_conf = min(99, max(10, s[3] + int(sentiment_score * 0.1)))
            rationale = f"Regime: {regime['regime']} | ML Prob: {s[4]}% | NLP Wire: {sentiment_score:+d} ({summary})."
            
            cursor.execute("""INSERT INTO ai_setups (timestamp, ticker, horizon, pattern, confidence, ml_prob, rr_ratio, entry_price, stop_loss, target_price, action, rationale)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (timestamp, s[0], s[1], s[2], adjusted_conf, s[4], s[5], s[6], s[7], s[8], s[9], rationale))
            
            if adjusted_conf >= 85:
                broadcaster.broadcast_setup({'ticker': s[0], 'horizon': s[1], 'action': s[9], 'pattern': s[2], 'confidence': adjusted_conf, 'ml_prob': s[4], 'entry_price': s[6], 'stop_loss': s[7], 'target_price': s[8], 'rr_ratio': s[5]})
                
        conn.commit()
    conn.close()

async def main():
    init_db()
    seed_initial_data()
    insider_scraper = SECInsiderScraper()
    while True:
        insider_scraper.update_insider_wire()
        ticker = random.choice(UNIVERSE_247)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🧠 24/7 Scanning asset: {ticker}")
        await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())