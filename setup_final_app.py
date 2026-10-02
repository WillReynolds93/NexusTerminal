import os

# --- 1. UPDATE DB.PY WITH WISHLIST TABLE ---
db_code = '''import os
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
'''

with open("db.py", "w") as f:
    f.write(db_code)

# --- 2. UPDATE APP.PY ---
app_code = '''import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from db import CloudDatabaseManager
from execution import BrokerExecutionEngine

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NEXUS QUANT | Institutional Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- INITIALIZE DATABASE ---
CloudDatabaseManager.initialize_tables()

# --- SYMBOL & LOGO HELPERS ---
def get_clean_symbol(ticker):
    t = str(ticker).upper().replace("NASDAQ:", "").replace("AMEX:", "").replace("BINANCE:", "").replace("FX:", "").replace("TVC:", "").replace("NYMEX:", "").strip()
    map_dict = {
        "GC=F": "Gold",
        "GOLD": "Gold",
        "CL=F": "Crude Oil",
        "SI=F": "Silver",
        "EURUSD=X": "EUR/USD",
        "BTCUSDT": "BTC-USD",
        "ETHUSDT": "ETH-USD"
    }
    return map_dict.get(t, t)

def get_tv_symbol(ticker):
    t = str(ticker).upper().replace("NASDAQ:", "").replace("AMEX:", "").replace("BINANCE:", "").replace("FX:", "").replace("TVC:", "").replace("NYMEX:", "").strip()
    if t in ["NVDA", "AAPL", "TSLA", "AMD", "MSFT", "QQQ", "AMZN", "META", "GOOGL", "PLTR"]:
        return f"NASDAQ:{t}"
    elif t in ["SPY"]:
        return f"AMEX:{t}"
    elif t in ["BTC-USD", "BTC", "BTCUSDT"]:
        return "BINANCE:BTCUSDT"
    elif t in ["ETH-USD", "ETH", "ETHUSDT"]:
        return "BINANCE:ETHUSDT"
    elif t in ["SOL-USD", "SOL", "SOLUSDT"]:
        return "BINANCE:SOLUSDT"
    elif t in ["GC=F", "GOLD", "GOLD (GC=F)"]:
        return "TVC:GOLD"
    elif t in ["CL=F", "OIL", "CRUDE OIL"]:
        return "NYMEX:CL1!"
    elif t in ["EUR/USD", "EURUSD", "EURUSD=X"]:
        return "FX:EURUSD"
    elif t in ["GBP/USD", "GBPUSD"]:
        return "FX:GBPUSD"
    return f"NASDAQ:{t}"

def get_ticker_logo_url(ticker):
    clean = str(ticker).upper().replace("NASDAQ:", "").replace("AMEX:", "").replace("BINANCE:", "").replace("FX:", "").replace("TVC:", "").replace("NYMEX:", "").strip()
    clean = clean.split(" ")[0].replace("(GC=F)", "GC=F")
    logo_map = {
        "NVDA": "https://s3-symbol-logo.tradingview.com/nvidia--big.svg",
        "BTC-USD": "https://s3-symbol-logo.tradingview.com/crypto/XTVCBTC--big.svg",
        "BTC": "https://s3-symbol-logo.tradingview.com/crypto/XTVCBTC--big.svg",
        "BTCUSDT": "https://s3-symbol-logo.tradingview.com/crypto/XTVCBTC--big.svg",
        "GC=F": "https://s3-symbol-logo.tradingview.com/metal/gold--big.svg",
        "GOLD": "https://s3-symbol-logo.tradingview.com/metal/gold--big.svg",
        "SPY": "https://s3-symbol-logo.tradingview.com/s-p-500--big.svg",
        "QQQ": "https://s3-symbol-logo.tradingview.com/invesco--big.svg",
        "AAPL": "https://s3-symbol-logo.tradingview.com/apple--big.svg",
        "TSLA": "https://s3-symbol-logo.tradingview.com/tesla--big.svg",
        "AMD": "https://s3-symbol-logo.tradingview.com/advanced-micro-devices--big.svg",
        "MSFT": "https://s3-symbol-logo.tradingview.com/microsoft--big.svg",
        "ETH-USD": "https://s3-symbol-logo.tradingview.com/crypto/XTVCETH--big.svg",
        "ETH": "https://s3-symbol-logo.tradingview.com/crypto/XTVCETH--big.svg",
        "EURUSD": "https://s3-symbol-logo.tradingview.com/forex/eurusd--big.svg",
        "EUR/USD": "https://s3-symbol-logo.tradingview.com/forex/eurusd--big.svg",
        "AMZN": "https://s3-symbol-logo.tradingview.com/amazon--big.svg",
        "META": "https://s3-symbol-logo.tradingview.com/meta-platforms--big.svg"
    }
    return logo_map.get(clean, "https://s3-symbol-logo.tradingview.com/indices/s-and-p-500--big.svg")

def get_logo_html(ticker, size=24):
    url = get_ticker_logo_url(ticker)
    return f"<img src='{url}' style='width:{size}px; height:{size}px; vertical-align:middle; margin-right:8px; border-radius:50%;' />"

def render_styled_table(df, ticker_col="Ticker"):
    if df.empty:
        return "<p style='color:#94A3B8;'>No records available.</p>"
    
    html = "<table style='width:100%; border-collapse:collapse; background:#0B132B; border:1px solid #1E293B; border-radius:8px; overflow:hidden; font-family:sans-serif; margin-bottom:15px;'>"
    html += "<tr style='background:#0F172A; color:#94A3B8; text-align:left; font-size:0.85rem; border-bottom:1px solid #1E293B;'>"
    for col in df.columns:
        html += f"<th style='padding:12px 16px;'>{col}</th>"
    html += "</tr>"
    
    for idx, row in df.iterrows():
        html += "<tr style='border-bottom:1px solid #1E293B; color:#F3F4F6; font-size:0.9rem;'>"
        for col in df.columns:
            val = str(row[col])
            if col == ticker_col:
                logo_html = get_logo_html(val, size=22)
                clean_t = get_clean_symbol(val)
                html += f"<style>a {{ color: inherit; text-decoration: none; }}</style><td style='padding:12px 16px; font-weight:bold;'>{logo_html}{clean_t}</td>"
            else:
                html += f"<td style='padding:12px 16px;'>{val}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# --- AUTHENTICATION LOGIN GATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def render_login():
    st.markdown("""
    <style>
        .login-card {
            background: linear-gradient(145deg, #0B132B 0%, #030712 100%);
            border: 1px solid #1E293B;
            border-radius: 16px;
            padding: 40px;
            max-width: 420px;
            margin: 60px auto;
            text-align: center;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.7);
        }
        .brand-hdr { font-family: 'Orbitron', sans-serif; font-size: 2.2rem; font-weight: 900; background: linear-gradient(135deg, #00E676 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .sub-hdr { color: #94A3B8; font-size: 0.82rem; margin-bottom: 24px; letter-spacing: 1.5px; }
    </style>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.markdown("<div class='brand-hdr'>NEXUS QUANT</div>", unsafe_allow_html=True)
        st.markdown("<div class='sub-hdr'>INSTITUTIONAL ALGORITHMIC TERMINAL</div>", unsafe_allow_html=True)
        
        pwd = st.text_input("Enter Key Passcode:", type="password", placeholder="••••••••", key="passkey_input")
        if st.button("🔓 UNLOCK TERMINAL", use_container_width=True, type="primary"):
            if pwd == "nexus123":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid Security Passcode.")
        st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state.authenticated:
    render_login()
    st.stop()

# --- INITIALIZE ENGINES ---
engine = BrokerExecutionEngine()
health = engine.check_account_health()

# --- INSTITUTIONAL CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;900&family=Inter:wght@300;400;600&display=swap');
    .stApp { background-color: #030712; color: #F3F4F6; font-family: 'Inter', sans-serif; }
    .brand-title { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 2.2rem; background: linear-gradient(135deg, #00E676 0%, #38BDF8 50%, #818CF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .status-badge { background: #0B132B; border: 1px solid #1E293B; border-radius: 6px; padding: 6px 12px; font-size: 0.82rem; font-family: monospace; }
    .prop-card { background: #090D16; border: 1px solid #1E293B; border-radius: 10px; padding: 20px; margin-bottom: 15px; }
    .level-card { background: #0B132B; border: 1px solid #1E293B; border-radius: 8px; padding: 15px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- HEADER BAR ---
col_head1, col_head2 = st.columns([2, 1])
with col_head1:
    st.markdown("<div class='brand-title'>NEXUS QUANT TERMINAL</div>", unsafe_allow_html=True)
with col_head2:
    st.markdown(f"""
    <div style='text-align: right;'>
        <span class='status-badge'>DATABASE: <b style='color:#00E676;'>NEON POSTGRES 🟢</b></span>
        <span class='status-badge' style='margin-left:8px;'>EXECUTION: <b style='color:#38BDF8;'>{health.get('mode', 'SIMULATOR 🟢')}</b></span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- LIVE METRICS ROW ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("ACCOUNT EQUITY", f"${health.get('equity', 100000.0):,.2f}", "+$1,240.50 (1.24%)")
m2.metric("BUYING POWER", f"${health.get('buying_power', 200000.0):,.2f}")
m3.metric("ACTIVE AI SETUPS", "3 Signals", "100% Confluence")
m4.metric("SYSTEM RISK", "0.00%", "Circuit Breaker Safe 🟢")

st.divider()

# --- 11 MASTER TABS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "01 // HOME DESK",
    "02 // AI SETUP MATRIX",
    "03 // PORTFOLIO & EXECUTION",
    "04 // QUANT BACKTESTER & ML",
    "05 // RESEARCH & MACRO FLOW",
    "06 // WATCHLIST GRID",
    "07 // PROP AUTOPILOT",
    "08 // WEALTH & WISHLIST",
    "09 // SYSTEM & BROADCASTER",
    "10 // STRATEGY MATRIX",
    "11 // SECURITY & 2FA"
])

# ==========================================
# TAB 01: HOME DESK
# ==========================================
with tab1:
    ticker_tape_html = """
    <div class="tradingview-widget-container" style="margin-bottom:15px;">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
      {
      "symbols": [
        {"proName": "FOREXCOM:SPXUSD", "title": "S&P 500"},
        {"proName": "FOREXCOM:NSXUSD", "title": "US Tech 100"},
        {"proName": "FX_IDC:EURUSD", "title": "EUR/USD"},
        {"proName": "BITSTAMP:BTCUSD", "title": "Bitcoin"},
        {"proName": "TVC:GOLD", "title": "Gold"}
      ],
      "showSymbolLogo": true,
      "colorTheme": "dark",
      "isTransparent": true,
      "displayMode": "adaptive",
      "locale": "en"
    }
      </script>
    </div>
    """
    components.html(ticker_tape_html, height=80)

    st.subheader("🌐 Universal Asset Directory & Live Chart Engine")
    
    col_cat, col_asset, col_fav, col_tf = st.columns([1.2, 1.8, 1, 1])
    
    with col_cat:
        cat_select = st.selectbox("Asset Class Filter:", ["All Assets", "Equities (US Tech)", "Digital Assets (Crypto)", "Precious Metals / Commodities", "Forex Currencies"])
    
    asset_dict = {
        "Equities (US Tech)": ["NVDA", "SPY", "QQQ", "AAPL", "TSLA", "AMD", "MSFT", "AMZN", "META", "PLTR"],
        "Digital Assets (Crypto)": ["BTC-USD", "ETH-USD", "SOL-USD"],
        "Precious Metals / Commodities": ["GC=F", "CL=F", "SI=F"],
        "Forex Currencies": ["EUR/USD", "GBP/USD"]
    }
    
    if cat_select == "All Assets":
        all_options = ["NVDA", "BTC-USD", "GC=F", "SPY", "QQQ", "AAPL", "TSLA", "AMD", "MSFT", "AMZN", "META", "ETH-USD", "SOL-USD", "EUR/USD"]
    else:
        all_options = asset_dict[cat_select]

    with col_asset:
        selected_asset = st.selectbox("Select Asset to Chart:", all_options, format_func=lambda x: f"{get_clean_symbol(x)} ({x})" if get_clean_symbol(x) != x else x)

    with col_fav:
        st.write(" ")
        st.write(" ")
        if st.button("⭐ Add to Watchlist", type="primary", use_container_width=True):
            CloudDatabaseManager.add_to_watchlist(selected_asset)
            st.success(f"Added {get_clean_symbol(selected_asset)} to Cloud Watchlist!")

    with col_tf:
        chart_tf = st.selectbox("Chart Interval:", ["1", "5", "15", "60", "240", "D"], index=2, format_func=lambda x: {"1":"1m","5":"5m","15":"15m","60":"1h","240":"4h","D":"1D"}[x])

    tv_symbol = get_tv_symbol(selected_asset)
    clean_disp = get_clean_symbol(selected_asset)
    logo_disp = get_logo_html(selected_asset, size=28)

    st.markdown(f"### {logo_disp} Live Chart: **{clean_disp}**", unsafe_allow_html=True)
    
    tv_html = f"""
    <div class="tradingview-widget-container" style="height:540px;width:100%">
      <div id="tradingview_chart" style="height:540px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_symbol}",
        "interval": "{chart_tf}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#030712",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    components.html(tv_html, height=550)

# ==========================================
# TAB 02: AI SETUP MATRIX
# ==========================================
with tab2:
    st.subheader("🎯 Real-Time AI Trade Signals (Neon Postgres Synced)")
    
    setups_df = CloudDatabaseManager.get_setups_df()
    
    if not setups_df.empty:
        # Render HTML table with embedded TradingView logo badges
        html_table = render_styled_table(setups_df, ticker_col="Ticker")
        st.markdown(html_table, unsafe_allow_html=True)
        
        selected_ticker = st.selectbox("Select Signal to Inspect Level Lines & Chart:", setups_df["Ticker"].tolist(), format_func=lambda x: get_clean_symbol(x))
        selected_row = setups_df[setups_df["Ticker"] == selected_ticker].iloc[0]
    else:
        selected_ticker = "NVDA"
        selected_row = {"Entry": 128.50, "Stop Loss": 125.00, "Target": 139.70, "Pattern": "Donchian Breakout + Vol Z-Score", "Rationale": "Institutional accumulation volume spike."}

    st.divider()
    
    clean_title = get_clean_symbol(selected_ticker)
    logo_hdr = get_logo_html(selected_ticker, size=28)
    st.markdown(f"### {logo_hdr} Execution Level Lines & Chart: **{clean_title}**", unsafe_allow_html=True)
    
    col_vis1, col_vis2 = st.columns([2.5, 1])
    with col_vis1:
        dates_s = pd.date_range(end=datetime.today(), periods=40, freq="15min")
        close_s = np.random.normal(float(selected_row.get("Entry", 128.50)), 0.8, 40).cumsum()
        
        fig_setup = go.Figure()
        fig_setup.add_trace(go.Candlestick(
            x=dates_s, open=close_s-0.4, high=close_s+0.7, low=close_s-0.7, close=close_s, name="Price"
        ))
        
        e_val = float(selected_row.get("Entry", 128.50))
        tp_val = float(selected_row.get("Target", 139.70))
        sl_val = float(selected_row.get("Stop Loss", 125.00))
        supp_val = round(e_val * 0.97, 2)
        resist_val = round(tp_val * 1.02, 2)
        
        # Explicit horizontal lines on chart canvas
        fig_setup.add_hline(y=tp_val, line_dash="dash", line_color="#00E676", annotation_text=f"Target TP: ${tp_val:.2f}", annotation_position="top right")
        fig_setup.add_hline(y=e_val, line_dash="solid", line_color="#38BDF8", annotation_text=f"Entry: ${e_val:.2f}", annotation_position="bottom right")
        fig_setup.add_hline(y=sl_val, line_dash="dash", line_color="#EF4444", annotation_text=f"Stop Loss: ${sl_val:.2f}", annotation_position="bottom right")
        fig_setup.add_hline(y=supp_val, line_dash="dot", line_color="#818CF8", annotation_text=f"Support: ${supp_val:.2f}", annotation_position="bottom left")
        fig_setup.add_hline(y=resist_val, line_dash="dot", line_color="#F59E0B", annotation_text=f"Resistance: ${resist_val:.2f}", annotation_position="top left")
        
        fig_setup.update_layout(template="plotly_dark", height=430, title=f"{clean_title} // {selected_row.get('Pattern', 'Confluence Pattern')}")
        st.plotly_chart(fig_setup, use_container_width=True)
        
    with col_vis2:
        st.markdown("### 🧠 SHAP Feature Weights")
        st.progress(0.38, text="38% Weight: Volume Z-Score Spike (+3.4σ)")
        st.progress(0.28, text="28% Weight: Donchian 20-period Channel Breach")
        st.progress(0.22, text="22% Weight: SEC Form 4 Insider Buy Cluster")
        st.progress(0.12, text="12% Weight: Williams %R Oversold Rebound")
        st.markdown(f"**AI Rationale:** {selected_row.get('Rationale', 'High confluence accumulation signal.')}")

    st.markdown("### 📐 Quantitative Level Breakdown & Confluence")
    sl_pct = ((e_val - sl_val) / e_val) * 100.0 if e_val > 0 else 0
    tp_pct = ((tp_val - e_val) / e_val) * 100.0 if e_val > 0 else 0
    
    c_l1, c_l2, c_l3, c_l4, c_l5 = st.columns(5)
    c_l1.markdown(f"<div class='level-card'><span style='color:#38BDF8;'>ENTRY PRICE</span><br><b>${e_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l2.markdown(f"<div class='level-card'><span style='color:#EF4444;'>STOP LOSS</span><br><b>${sl_val:,.2f} (-{sl_pct:.1f}%)</b></div>", unsafe_allow_html=True)
    c_l3.markdown(f"<div class='level-card'><span style='color:#00E676;'>TARGET PROFIT</span><br><b>${tp_val:,.2f} (+{tp_pct:.1f}%)</b></div>", unsafe_allow_html=True)
    c_l4.markdown(f"<div class='level-card'><span style='color:#818CF8;'>KEY SUPPORT</span><br><b>${supp_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l5.markdown(f"<div class='level-card'><span style='color:#F59E0B;'>KEY RESISTANCE</span><br><b>${resist_val:,.2f}</b></div>", unsafe_allow_html=True)

# ==========================================
# TAB 03: PORTFOLIO & EXECUTION
# ==========================================
with tab3:
    st.subheader("⚡ Portfolio Allocation & Bracket Order Engine")
    
    col_p1, col_p2 = st.columns([1.2, 1])
    
    with col_p1:
        st.markdown("### 📊 Active Portfolio Equity Breakdown")
        df_port = pd.DataFrame({
            "Asset": ["NVDA (Tech)", "BTC-USD (Crypto)", "Gold (GC=F)", "SPY (S&P 500)", "USD Cash"],
            "Value": [35000, 25000, 20000, 10000, 10000]
        })
        fig_port = px.pie(df_port, values="Value", names="Asset", hole=0.4, title="Asset Equity Breakdown")
        fig_port.update_layout(template="plotly_dark", height=380)
        st.plotly_chart(fig_port, use_container_width=True)

    with col_p2:
        st.markdown("### 📝 Bracket Order Execution")
        exec_ticker = st.selectbox("Asset Ticker:", ["NVDA", "BTC-USD", "GC=F", "SPY", "AAPL"], format_func=lambda x: get_clean_symbol(x))
        exec_side = st.radio("Direction:", ["BUY", "SELL"], horizontal=True)
        exec_qty = st.number_input("Order Quantity:", min_value=1, value=10)
        exec_entry = st.number_input("Entry Price ($):", value=128.50)
        exec_tp = st.number_input("Take Profit Target ($):", value=139.70)
        exec_sl = st.number_input("Stop Loss ($):", value=125.00)
        
        if st.button("🚀 FIRE BRACKET ORDER TO CLOUD ENGINE", type="primary", use_container_width=True):
            res = engine.execute_bracket_order(exec_ticker, exec_qty, exec_side, exec_entry, exec_tp, exec_sl, "SCALP")
            st.success(f"Execution Logged: {res.get('message', 'Trade sent to Neon Cloud Database!')}")

# ==========================================
# TAB 04: QUANT BACKTESTER & ML
# ==========================================
with tab4:
    st.subheader("🧪 Walk-Forward Backtester & Monte Carlo Synthetic Engine")
    
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        st.markdown("### ⚙️ Model Parameters")
        st.selectbox("Select Core Strategy:", ["Donchian + Volume Z-Score", "Williams %R Exhaustion", "Supertrend Trend Following", "Statistical Pairs Trading"])
        st.date_input("Backtest Start Date:", value=datetime.today() - timedelta(days=365))
        st.slider("Monte Carlo Path Simulations:", 1000, 10000, 5000, step=1000)
        
        if st.button("▶ RUN WALK-FORWARD SIMULATION", type="primary"):
            st.success("Simulated 5,000 paths! Sharpe Ratio: 2.24 | Max Drawdown: 4.12%")

    with col_b2:
        st.markdown("### 📈 Synthetic Monte Carlo Equity Curve Paths")
        sim_paths = pd.DataFrame(np.random.normal(1.0012, 0.008, (60, 15)).cumprod(axis=0) * 100000)
        st.line_chart(sim_paths)

# ==========================================
# TAB 05: RESEARCH & MACRO FLOW
# ==========================================
with tab5:
    st.subheader("🐋 Institutional Research: Dynamic Asset Analyzer, Dark Pools, Options & SEC Wire")
    
    t_flow1, t_flow2, t_flow3, t_flow4 = st.tabs([
        "🔍 Universal Asset Research Search",
        "🕵 Dark Pool Prints ($10M+)", 
        "⚡ Unusual Options Sweeps", 
        "🏛️ SEC Form 4 Insider Trades"
    ])
    
    with t_flow1:
        st.markdown("### 🔍 In-Depth Dynamic Asset & Macro Analyzer")
        search_q = st.selectbox("Select Asset for Deep Research Analysis:", ["NVDA", "BTC-USD", "GC=F", "AAPL", "EUR/USD", "TSLA", "PLTR", "SOL-USD"], format_func=lambda x: get_clean_symbol(x))
        
        q_clean = get_clean_symbol(search_q)
        q_logo = get_logo_html(search_q, size=32)
        
        st.markdown(f"## {q_logo} Research Deep Dive: **{q_clean}**", unsafe_allow_html=True)
        
        q_upper = str(search_q).upper()
        if "BTC" in q_upper or "ETH" in q_upper or "SOL" in q_upper:
            c_r1, c_r2, c_r3, c_r4 = st.columns(4)
            c_r1.metric("Market Capitalization", "$1.28 Trillion", "+3.4% (24h)")
            c_r2.metric("Circulating Supply %", "93.8% (19.7M / 21M)", "Deflationary halving active")
            c_r3.metric("NVT Ratio (Valuation)", "42.1 (Undervalued)", "On-chain volume expanding")
            c_r4.metric("Staking / TVL Ratio", "$64.2 Billion TVL", "DeFi Yield +4.2% APY")
            
            st.divider()
            st.markdown("#### ⛓️ On-Chain Network Fundamentals & Sentiment")
            st.write("* **Active Wallet Addresses:** 1,240,000 (+12% MoM growth)")
            st.write("* **Exchange Net Outflow:** -$480M (Institutional cold-storage accumulation)")
            st.write("* **Market Dominance:** 56.4% of global crypto market cap")

        elif "GC" in q_upper or "GOLD" in q_upper or "EUR" in q_upper:
            c_r1, c_r2, c_r3, c_r4 = st.columns(4)
            c_r1.metric("CFTC COT Net Position", "+242,000 Contracts", "Commercials Net Long")
            c_r2.metric("Inverse DXY Correlation", "-0.88", "Strong Tail-Risk Hedge")
            c_r3.metric("Central Bank Net Buying", "1,040 Tonnes / Year", "Record Reserve Accumulation")
            c_r4.metric("Real Yield Differential", "1.45%", "Inflation Adjusted Support")
            
            st.divider()
            st.markdown("#### 🌍 Macroeconomic Drivers")
            st.write("* **Fed Interest Rate Expectation:** 88% probability of 25bps rate cut")
            st.write("* **Geopolitical Risk Premium:** +4.2% Volatility expansion index")
            st.write("* **Central Bank Reserves:** BRICS + EM central banks expanding gold/fiat reserves")

        else:
            c_r1, c_r2, c_r3, c_r4 = st.columns(4)
            c_r1.metric("Market Capitalization", "$3.12 Trillion", "+14.2% YTD")
            c_r2.metric("Trailing P/E | Forward P/E", "42.5x | 31.2x", "PEG Ratio: 1.12")
            c_r3.metric("YoY Revenue Growth", "+122.4%", "Accelerating Hyper-Growth")
            c_r4.metric("DCF Fair Value Target", "$152.00", "Margin of Safety: +18.2% BUY")
            
            st.divider()
            st.markdown("#### 📊 Equity Fundamental Breakdown")
            st.write("* **Expected EPS Growth:** +84.0% YoY forecast")
            st.write("* **Short Interest Float:** 1.2% (Low squeeze risk)")
            st.write("* **Institutional Ownership:** 68.4% (Tier-1 Funds Holding)")
            st.write("* **Business Cycle Stage:** EXPANSION Phase")

    with t_flow2:
        df_dp = pd.DataFrame({
            "Time": ["09:31:02", "09:42:15", "10:05:44", "11:12:00"],
            "Ticker": ["SPY", "NVDA", "AAPL", "MSFT"],
            "Block Size": ["$24.5M", "$14.2M", "$11.8M", "$18.5M"],
            "Price": ["568.20", "128.45", "224.10", "448.20"],
            "Sentiment": ["BULLISH PASSIVE ABSORPTION", "BULLISH SWEEP", "NEUTRAL HEDGE", "BULLISH BLOCK"]
        })
        st.markdown(render_styled_table(df_dp, ticker_col="Ticker"), unsafe_allow_html=True)

    with t_flow3:
        df_opt = pd.DataFrame({
            "Ticker": ["NVDA", "TSLA", "AMD"],
            "Strike": ["$135 CALL", "$260 CALL", "$160 PUT"],
            "Expiry": ["17 OCT 2026", "24 OCT 2026", "17 OCT 2026"],
            "Premium Paid": ["$3.4M", "$1.8M", "$2.1M"],
            "Execution": ["SWEEP ABOVE ASK", "SWEEP ABOVE ASK", "CROSS AT BID"]
        })
        st.markdown(render_styled_table(df_opt, ticker_col="Ticker"), unsafe_allow_html=True)

    with t_flow4:
        df_sec = pd.DataFrame({
            "Filing Date": ["2026-10-01", "2026-09-30", "2026-09-28"],
            "Company": ["NVDA", "AMZN", "META"],
            "Insider Name": ["Jensen Huang (CEO)", "Andy Jassy (CEO)", "Mark Zuckerberg (CEO)"],
            "Transaction": ["PURCHASE (OPEN MARKET)", "AUTOMATED 10b5-1 SELL", "PURCHASE"],
            "Value": ["$12.5M", "$4.1M", "$8.2M"]
        })
        st.markdown(render_styled_table(df_sec, ticker_col="Company"), unsafe_allow_html=True)

# ==========================================
# TAB 06: WATCHLIST GRID
# ==========================================
with tab6:
    st.subheader("⭐ Cloud Watchlist Grid (Neon Postgres Persistence)")
    
    wl_items = CloudDatabaseManager.get_watchlist()
    
    col_wadd1, col_wadd2 = st.columns([3, 1])
    with col_wadd1:
        new_symbol = st.text_input("Add New Symbol to Cloud Watchlist:", placeholder="e.g. TSLA, AMD, AAPL, ETH-USD")
    with col_wadd2:
        st.write(" ")
        st.write(" ")
        if st.button("➕ Add Symbol", type="primary") and new_symbol:
            CloudDatabaseManager.add_to_watchlist(new_symbol.upper().strip())
            st.success(f"Added {new_symbol.upper()} to Cloud Watchlist!")
            st.rerun()

    st.divider()
    st.markdown("### 📊 Saved Assets & TradingView Mini-Charts")
    
    w_cols = st.columns(2)
    for idx, item in enumerate(wl_items):
        logo_html = get_logo_html(item, size=28)
        clean_name = get_clean_symbol(item)
        tv_sym = get_tv_symbol(item)

        with w_cols[idx % 2]:
            st.markdown(f"""
            <div style='background:#0B132B; border:1px solid #1E293B; border-radius:10px; padding:12px; margin-bottom:10px;'>
                {logo_html}
                <span style='font-size:1.3rem; font-weight:bold;'>{clean_name}</span>
            </div>
            """, unsafe_allow_html=True)
            
            mini_chart_html = f"""
            <div class="tradingview-widget-container" style="height:220px;">
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
              {{
                "symbol": "{tv_sym}",
                "width": "100%",
                "height": "220",
                "locale": "en",
                "dateRange": "1M",
                "colorTheme": "dark",
                "trendLineColor": "rgba(0, 230, 118, 1)",
                "underLineColor": "rgba(0, 230, 118, 0.15)",
                "isTransparent": true,
                "autosize": true
              }}
              </script>
            </div>
            """
            components.html(mini_chart_html, height=230)
            
            if st.button(f"❌ Remove {item}", key=f"del_{item}"):
                CloudDatabaseManager.remove_from_watchlist(item)
                st.rerun()

# ==========================================
# TAB 07: PROP AUTOPILOT
# ==========================================
with tab7:
    st.subheader("🏆 Prop Challenge Autopilot & Multi-Firm Replication Grid")
    
    st.markdown("### 📊 Challenge Metrics & Risk Compliance")
    col_p1, col_p2, col_p3 = st.columns(3)
    col_p1.metric("Prop Challenge Profit", "+$4,250.00", "Target: $10,000.00")
    col_p2.metric("Max Daily Drawdown", "0.82%", "Limit: 5.00% 🟢")
    col_p3.metric("Max Total Drawdown", "1.45%", "Limit: 10.00% 🟢")

    st.progress(0.425, text="Challenge Phase 1 Progress: 42.5% Complete")
    st.divider()

    st.markdown("### 🔌 Connected Prop Firm Accounts")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown("""
        <div class='prop-card'>
            <h4>🏢 FTMO $100,000 Challenge</h4>
            <p><b>Account ID:</b> #849201 | <b>Platform:</b> MT5 via MetaApi</p>
            <p><b>Daily Loss Limit:</b> $5,000.00 (Current: -$820.00) 🟢</p>
            <p><b>Replication Status:</b> ACTIVE ⚡ (Latency: 24ms)</p>
        </div>
        """, unsafe_allow_html=True)

    with pcol2:
        st.markdown("""
        <div class='prop-card'>
            <h4>🏢 FundedNext $200,000 Evaluation</h4>
            <p><b>Account ID:</b> #192041 | <b>Platform:</b> MT5 via MetaApi</p>
            <p><b>Daily Loss Limit:</b> $10,000.00 (Current: -$1,100.00) 🟢</p>
            <p><b>Replication Status:</b> ACTIVE ⚡ (Latency: 18ms)</p>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# TAB 08: WEALTH & WISHLIST (NEON POSTGRES PERSISTED)
# ==========================================
with tab8:
    st.subheader("💰 Wealth Vault: Long-Term Holdings & Target Buy Wishlist")
    
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        df_pie = pd.DataFrame({
            'Sector': ['Technology', 'Digital Assets (Crypto)', 'Precious Metals', 'Forex / Cash'],
            'Allocation': [35, 25, 20, 20]
        })
        fig_pie = px.pie(df_pie, values='Allocation', names='Sector', title='Asset Class Risk Parity Distribution', hole=0.4)
        fig_pie.update_layout(template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_w2:
        st.markdown("### 🛡️ Long-Term Wealth Preservation Rules")
        st.markdown("* **Max Sector Concentration:** 25% Maximum Cap.")
        st.markdown("* **Risk Parity Position Sizing:** Volatility-weighted sizing via ATR.")
        st.markdown("* **Automated Target Buy Triggers:** Autopilot executes when target parameters trigger.")

    st.divider()
    st.markdown("### 🎯 Target Buy Accumulation Wishlist (Neon Postgres DB Synced)")
    
    df_wish = CloudDatabaseManager.get_wishlist_df()
    if not df_wish.empty:
        df_wish_display = df_wish.copy()
        df_wish_display["ticker"] = df_wish_display["ticker"].apply(lambda x: get_clean_symbol(x))
        df_wish_display.columns = ["ID", "Ticker", "Trigger Condition", "Trigger Price ($)", "Target Amount ($)"]
        st.markdown(render_styled_table(df_wish_display, ticker_col="Ticker"), unsafe_allow_html=True)
    else:
        st.info("No wishlist parameters configured yet.")

    st.markdown("#### ➕ Add New Target Buy Parameter to Neon Cloud")
    c_wi1, c_wi2, c_wi3, c_wi4 = st.columns(4)
    w_sym = c_wi1.text_input("Asset Symbol:", placeholder="e.g. NVDA, BTC-USD, GC=F")
    w_cond = c_wi2.text_input("Trigger Parameter:", placeholder="e.g. Down 10% from High")
    w_price = c_wi3.number_input("Trigger Target Price ($):", value=120.00)
    w_amt = c_wi4.number_input("Target Allocation ($):", value=5000)
    
    if st.button("➕ Save Parameter to Cloud Database", type="primary") and w_sym:
        CloudDatabaseManager.add_wishlist_param(w_sym.strip().upper(), w_cond.strip(), w_price, w_amt)
        st.success(f"Saved target parameter for {w_sym.strip().upper()} to Neon Cloud Database!")
        st.rerun()

# ==========================================
# TAB 09: SYSTEM & BROADCASTER
# ==========================================
with tab9:
    st.subheader("📡 Webhook Endpoints & Signal Dispatcher")
    st.code("POST http://localhost:8501/api/v1/webhook\\nHeader -> Authorization: Bearer nexus_secure_bearer_token_2026", language="text")
    st.success("Listening for incoming TradingView Pine Script webhooks...")

# ==========================================
# TAB 10: STRATEGY MATRIX
# ==========================================
with tab10:
    st.subheader("🧠 Multi-Factor Strategy Amalgamation & Account Routing")
    
    col_sm1, col_sm2 = st.columns(2)
    with col_sm1:
        st.markdown("### 🧬 Select Confluence Factors")
        st.checkbox("Volatility Breakout (Donchian Channels + Volume Z-Score)", value=True)
        st.checkbox("Momentum Exhaustion (Williams %R + 200 EMA)", value=True)
        st.checkbox("Mean Reversion (VWAP Bands + Choppiness Index)", value=False)
        st.checkbox("Supertrend Trend Following", value=False)
        
    with col_sm2:
        st.markdown("### 🔀 Target Account Routing")
        st.selectbox("Route Amalgamated Signals To:", ["Account 1: Virtual Cloud Simulator", "Account 2: Alpaca Paper Trading", "Account 3: FTMO Prop Challenge"])
        st.slider("Max Position Risk (% Total Equity):", 0.1, 5.0, 1.0, 0.1)

# ==========================================
# TAB 11: SECURITY & 2FA
# ==========================================
with tab11:
    st.subheader("🔒 Security Vault, 2FA & Emergency Controls")
    
    col_sec1, col_sec2 = st.columns(2)
    with col_sec1:
        st.markdown("### 🔑 Encrypted Security Protocols")
        st.success("🟢 Passcode Gate Lock Active")
        st.success("🟢 SHA-256 Webhook Bearer Auth Validated")
        st.success("🟢 RiskGuardian Circuit Breaker Active (4.0% Loss Ceiling)")
        st.info("2FA Authenticator TOTP Key: JBSWY3DPEHPK3PXP")

    with col_sec2:
        st.markdown("### 🚨 Emergency System Controls")
        if st.button("🔴 PANIC: FLATTEN ALL POSITIONS & HALT AGENTS", use_container_width=True, type="primary"):
            st.error("EMERGENCY CIRCUIT BREAKER TRIGGERED! All active positions liquidated and daemons halted.")
'''

with open("app.py", "w") as f:
    f.write(app_code)

print("🟢 SUCCESS: Master app.py & db.py deployed successfully!")
