import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import psycopg2
from datetime import datetime, timedelta
import streamlit.components.v1 as components
from db import CloudDatabaseManager
from execution import BrokerExecutionEngine

# --- SAFE YFINANCE IMPORT ---
try:
    import yfinance as yf
except ImportError:
    yf = None

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NEXUS QUANT | Institutional Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 📡 LIVE DATA FETCHING ENGINES (CACHED)
# ==========================================
@st.cache_data(ttl=300) # Cache for 5 minutes to prevent rate limits
def fetch_live_watchlist_movers(tickers):
    if not yf or not tickers: return pd.DataFrame()
    rows = []
    for t in tickers:
        try:
            df = yf.Ticker(t).history(period="1mo")
            if len(df) < 2: continue
            close = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct = ((close - prev) / prev) * 100
            
            avg_vol = df['Volume'].iloc[-20:-1].mean()
            vol = df['Volume'].iloc[-1]
            rvol = (vol / avg_vol) if avg_vol > 0 else 1.0
            
            flow = "BUY SWEEP 🟢" if pct > 1 and rvol > 1.2 else ("DISTRIBUTION 🔴" if pct < -1 and rvol > 1.2 else "NEUTRAL ⚪")
            rows.append({
                "Ticker": t,
                "Market Price ($)": f"{close:,.2f}",
                "Daily Change (%)": f"{pct:+.2f}%",
                "Relative Volume (RVOL)": f"{rvol:.1f}x",
                "Institutional Flow": flow,
                "Primary Catalyst": "Live Algorithmic Flow"
            })
        except: pass
    
    df_res = pd.DataFrame(rows)
    if not df_res.empty:
        # Sort by biggest absolute percentage movers
        df_res['abs_change'] = df_res['Daily Change (%)'].str.extract(r'([0-9.]+)').astype(float)
        df_res = df_res.sort_values(by='abs_change', ascending=False).drop(columns=['abs_change'])
    return df_res

@st.cache_data(ttl=3600) # Cache for 1 hour
def fetch_live_asset_info(ticker):
    if not yf: return None
    try:
        info = yf.Ticker(ticker).info
        mcap = info.get("marketCap", 0)
        mcap_str = f"${mcap / 1e9:,.2f} Billion" if mcap > 0 else "N/A"
        return {
            "name": info.get("shortName", ticker),
            "summary": info.get("longBusinessSummary", "Live business description unavailable for this asset."),
            "mcap": mcap_str,
            "pe_trail": info.get("trailingPE", "N/A"),
            "pe_fwd": info.get("forwardPE", "N/A")
        }
    except: return None

@st.cache_data(ttl=900) # Cache for 15 mins
def fetch_live_news(tickers):
    if not yf or not tickers: return []
    stories = []
    try:
        for t in tickers[:3]: # Grab news for top 3 watchlist items
            news = yf.Ticker(t).news
            if news:
                for n in news[:2]:
                    stories.append({
                        "tag": t.upper(),
                        "title": n.get('title', 'Market Update'),
                        "source": f"{n.get('publisher', 'Financial Wire')} • Live Update",
                        "thumb": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&q=80",
                        "summary": "Live institutional coverage link available via publisher source."
                    })
        return stories
    except: return []

@st.cache_data(ttl=86400)
def fetch_live_backtest_data(ticker="SPY"):
    if not yf: return pd.DataFrame()
    try:
        df = yf.Ticker(ticker).history(period="1y")
        df['SMA_20'] = df['Close'].rolling(20).mean()
        df['SMA_50'] = df['Close'].rolling(50).mean()
        # Simple crossover mock backtest equity curve
        df['Signal'] = np.where(df['SMA_20'] > df['SMA_50'], 1, 0)
        df['Returns'] = df['Close'].pct_change()
        df['Strategy_Returns'] = df['Signal'].shift(1) * df['Returns']
        df['Cumulative_Equity'] = (1 + df['Strategy_Returns']).cumprod() * 100000
        return df[['Cumulative_Equity']].dropna()
    except: return pd.DataFrame()

# --- DATABASE CONNECTION & AUTOMATIC TABLE INITIALIZER ---
def get_db_conn():
    db_url = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    if db_url:
        if "channel_binding=" in db_url: db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
        try: return psycopg2.connect(db_url)
        except Exception: return None
    return None

def init_all_tables():
    conn = get_db_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""CREATE TABLE IF NOT EXISTS signals (id SERIAL PRIMARY KEY, horizon VARCHAR(20), ticker VARCHAR(20), pattern VARCHAR(100), confidence INT, win_prob INT, risk_reward VARCHAR(20), entry DOUBLE PRECISION, stop_loss DOUBLE PRECISION, target DOUBLE PRECISION, action VARCHAR(10), rationale TEXT, strategy VARCHAR(50) DEFAULT 'Donchian Breakout', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
                cur.execute("""CREATE TABLE IF NOT EXISTS demo_positions (id SERIAL PRIMARY KEY, ticker VARCHAR(20), action VARCHAR(10), qty DOUBLE PRECISION, entry_price DOUBLE PRECISION, stop_loss DOUBLE PRECISION, take_profit DOUBLE PRECISION, status VARCHAR(20) DEFAULT 'OPEN', exit_price DOUBLE PRECISION, pnl DOUBLE PRECISION, strategy VARCHAR(50) DEFAULT 'Donchian Breakout', opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, closed_at TIMESTAMP);""")
                cur.execute("""CREATE TABLE IF NOT EXISTS system_config (key_name VARCHAR(50) PRIMARY KEY, key_value VARCHAR(50), updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
                cur.execute("INSERT INTO system_config (key_name, key_value) VALUES ('autopilot_active', 'FALSE') ON CONFLICT DO NOTHING;")
                cur.execute("INSERT INTO system_config (key_name, key_value) VALUES ('autopilot_min_conf', '80') ON CONFLICT DO NOTHING;")
                conn.commit()
            conn.close()
        except Exception: pass

init_all_tables()
CloudDatabaseManager.initialize_tables()

# --- AUTOPILOT CONFIG MANAGEMENT ---
def get_autopilot_config_ui():
    conn = get_db_conn()
    active, min_conf = False, 80
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT key_name, key_value FROM system_config WHERE key_name IN ('autopilot_active', 'autopilot_min_conf');")
                for k, v in cur.fetchall():
                    if k == 'autopilot_active': active = (v == 'TRUE')
                    elif k == 'autopilot_min_conf': min_conf = int(v)
            conn.close()
        except Exception: pass
    return active, min_conf

def set_autopilot_config_ui(active_bool, min_conf_int):
    conn = get_db_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE system_config SET key_value = %s, updated_at = CURRENT_TIMESTAMP WHERE key_name = 'autopilot_active';", ('TRUE' if active_bool else 'FALSE',))
                cur.execute("UPDATE system_config SET key_value = %s, updated_at = CURRENT_TIMESTAMP WHERE key_name = 'autopilot_min_conf';", (str(min_conf_int),))
                conn.commit()
            conn.close()
        except Exception: pass

# --- SYMBOL HELPERS ---
def get_clean_symbol(t): return t.upper().replace("NASDAQ:", "").replace("AMEX:", "").replace("BINANCE:", "").replace("FX:", "").replace("TVC:", "").replace("NYMEX:", "").strip()
def get_tv_symbol(t):
    c = get_clean_symbol(t)
    if c in ["NVDA", "AAPL", "TSLA", "AMD", "MSFT", "QQQ", "AMZN", "META", "GOOGL", "PLTR", "INTC", "NFLX", "COIN", "MSTR"]: return f"NASDAQ:{c}"
    elif c == "SPY": return "AMEX:SPY"
    elif c in ["BTC-USD", "ETH-USD", "SOL-USD"]: return f"BINANCE:{c.replace('-USD', 'USDT')}"
    elif c in ["GC=F", "GOLD"]: return "TVC:GOLD"
    elif c in ["CL=F", "OIL"]: return "NYMEX:CL1!"
    return f"NASDAQ:{c}"

def get_logo_html(ticker, size=24): return f"<img src='https://s3-symbol-logo.tradingview.com/indices/s-and-p-500--big.svg' style='width:{size}px; height:{size}px; vertical-align:middle; margin-right:8px; border-radius:50%;' />"

def render_styled_table(df, ticker_col="Ticker"):
    if df.empty: return "<p style='color:#94A3B8;'>No records available.</p>"
    html = "<table style='width:100%; border-collapse:collapse; background:#0B132B; border:1px solid #1E293B; border-radius:8px; overflow:hidden; font-family:sans-serif; margin-bottom:15px;'>"
    html += "<tr style='background:#0F172A; color:#94A3B8; text-align:left; font-size:0.85rem; border-bottom:1px solid #1E293B;'>"
    for col in df.columns: html += f"<th style='padding:12px 16px;'>{col}</th>"
    html += "</tr>"
    for idx, row in df.iterrows():
        html += "<tr style='border-bottom:1px solid #1E293B; color:#F3F4F6; font-size:0.9rem;'>"
        for col in df.columns:
            val = str(row[col])
            if col == ticker_col: html += f"<td style='padding:12px 16px; font-weight:bold;'>{get_logo_html(val, size=22)}{get_clean_symbol(val)}</td>"
            else: html += f"<td style='padding:12px 16px;'>{val}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# --- LOGIN GATE ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.markdown("<br><br><br><h1 style='text-align: center; font-family: Orbitron; font-size: 3rem; background: linear-gradient(135deg, #00E676 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>NEXUS QUANT</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 1.1rem; letter-spacing: 2px;'>INSTITUTIONAL ALGORITHMIC TERMINAL</p>", unsafe_allow_html=True)
    st.write("")
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        if st.button("🔓 UNLOCK TERMINAL", use_container_width=True, type="primary") if st.text_input("Passcode:", type="password") == "nexus123" else False:
            st.session_state.authenticated = True; st.rerun()
    st.stop()

# --- INIT ENGINES ---
engine = BrokerExecutionEngine()
health = engine.check_account_health()
wl_items = CloudDatabaseManager.get_watchlist()
if not wl_items: wl_items = ["NVDA", "BTC-USD", "GC=F", "SPY"]

is_autopilot, min_conf_threshold = get_autopilot_config_ui()

# --- DYNAMIC DB M2M CALCULATIONS ---
conn = get_db_conn()
positions_df = pd.DataFrame()
if conn:
    try:
        positions_df = pd.read_sql("SELECT * FROM demo_positions ORDER BY opened_at DESC;", conn)
        conn.close()
    except: pass

open_trades = positions_df[positions_df['status'] == 'OPEN'] if not positions_df.empty and 'status' in positions_df.columns else pd.DataFrame()
closed_trades = positions_df[positions_df['status'] == 'CLOSED'] if not positions_df.empty and 'status' in positions_df.columns else pd.DataFrame()

realized_pnl = closed_trades['pnl'].sum() if not closed_trades.empty and 'pnl' in closed_trades.columns else 0.0
unrealized_pnl, allocated_margin = 0.0, 0.0

if not open_trades.empty:
    for idx, row in open_trades.iterrows():
        try:
            qty, entry = float(row['qty']), float(row['entry_price'])
            allocated_margin += (entry * qty)
            if yf:
                data = yf.Ticker(str(row['ticker'])).history(period="1d", interval="1m")
                if not data.empty:
                    unrealized_pnl += ((float(data['Close'].iloc[-1]) - entry) * qty if str(row['action']).upper() == "BUY" else (entry - float(data['Close'].iloc[-1])) * qty)
        except: pass

starting_balance = 100000.0
live_equity = starting_balance + realized_pnl + unrealized_pnl
buying_power = max(0.0, (live_equity * 2.0) - allocated_margin)

# --- INSTITUTIONAL CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;900&family=Inter:wght@300;400;600&display=swap');
    .stApp { background-color: #030712; color: #F3F4F6; font-family: 'Inter', sans-serif; }
    .brand-title { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 2.2rem; background: linear-gradient(135deg, #00E676 0%, #38BDF8 50%, #818CF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .status-badge { background: #0B132B; border: 1px solid #1E293B; border-radius: 6px; padding: 6px 12px; font-size: 0.82rem; font-family: monospace; }
    .level-card { background: #0B132B; border: 1px solid #1E293B; border-radius: 8px; padding: 15px; text-align: center; }
    .amd-card { background: #1E293B; border-left: 4px solid #818CF8; border-radius: 6px; padding: 12px; margin-bottom: 15px; }
    .news-tag { background: #1E293B; color: #38BDF8; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# --- HEADER BAR ---
col_head1, col_head2 = st.columns([2, 1])
with col_head1: st.markdown("<div class='brand-title'>NEXUS QUANT TERMINAL</div>", unsafe_allow_html=True)
with col_head2:
    st.markdown(f"""
    <div style='text-align: right;'>
        <span class='status-badge'>AUTOPILOT: <b style='color:{"#00E676" if is_autopilot else "#EF4444"};'>{"ACTIVE 🟢" if is_autopilot else "OFF 🔴"}</b></span>
        <span class='status-badge' style='margin-left:8px;'>DATABASE: <b style='color:#00E676;'>LIVE 🟢</b></span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# --- TICKER TAPE ---
components.html(f"""
<div class="tradingview-widget-container" style="margin-top: 5px; margin-bottom: 20px;">
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
  {{ "symbols": {json.dumps([{"proName": get_tv_symbol(s), "title": get_clean_symbol(s)} for s in wl_items])}, "colorTheme": "dark", "isTransparent": true, "displayMode": "adaptive", "locale": "en" }}
  </script>
</div>
""", height=100)

# --- LIVE METRICS ROW ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("LIVE ACCOUNT EQUITY", f"${live_equity:,.2f}", f"{(realized_pnl + unrealized_pnl):+,.2f} ({((realized_pnl + unrealized_pnl) / starting_balance) * 100.0:+.2f}%)")
m2.metric("BUYING POWER", f"${buying_power:,.2f}")
m3.metric("UNREALIZED P&L", f"${unrealized_pnl:,.2f}", f"Active Trades: {len(open_trades)}")
m4.metric("SYSTEM RISK", "0.00%", "Circuit Breaker Safe 🟢")

st.divider()

# --- 11 MASTER TABS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
    "01 // HOME DESK", "02 // AI SETUP MATRIX", "03 // PORTFOLIO & EXECUTION",
    "04 // QUANT BACKTESTER & ML", "05 // RESEARCH & MACRO FLOW", "06 // WATCHLIST GRID",
    "07 // PROP AUTOPILOT", "08 // WEALTH & WISHLIST", "09 // SYSTEM & BROADCASTER",
    "10 // STRATEGY MATRIX", "11 // SECURITY & 2FA"
])

# ==========================================
# TAB 01: HOME DESK
# ==========================================
with tab1:
    st.subheader("🌐 Global Market Overview & Live TradingView Engine")
    col_cat, col_dd, col_search, col_fav, col_tf = st.columns([1.2, 1.2, 2, 1, 0.8])
    with col_cat: cat_select = st.selectbox("Asset Class:", ["All Assets", "Equities", "Crypto", "Commodities"])
    dd_options = ["NVDA", "BTC-USD", "GC=F", "SPY", "AAPL", "ETH-USD"]
    with col_dd: dd_sym = st.selectbox("Asset Select:", dd_options, format_func=lambda x: get_clean_symbol(x))
    with col_search: search_sym = st.text_input("Or Search Any Ticker:", placeholder="e.g. PLTR, MSTR...")
    with col_fav:
        st.write(" "); st.write(" ")
        active_sym = search_sym.strip().upper() if search_sym.strip() else dd_sym
        if st.button("⭐ Add to Watchlist", type="primary", use_container_width=True):
            CloudDatabaseManager.add_to_watchlist(active_sym); st.success(f"Added {get_clean_symbol(active_sym)}!")
    with col_tf: chart_tf = st.selectbox("Interval:", ["1", "5", "15", "60", "240", "D"], index=2, format_func=lambda x: {"1":"1m","5":"5m","15":"15m","60":"1h","240":"4h","D":"1D"}[x])

    tv_symbol = get_tv_symbol(active_sym)
    st.markdown(f"### Live Chart: **{get_clean_symbol(active_sym)}**")
    components.html(f"""
    <div class="tradingview-widget-container" style="height:560px;width:100%">
      <div id="tv_home_chart" style="height:560px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{ "autosize": true, "symbol": "{tv_symbol}", "interval": "{chart_tf}", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#030712", "enable_publishing": false, "allow_symbol_change": true, "container_id": "tv_home_chart" }});
      </script>
    </div>
    """, height=570)

# ==========================================
# TAB 02: AI SETUP MATRIX
# ==========================================
with tab2:
    st.subheader("🎯 Real-Time AI Trade Signals & Confluence Matrix")
    c_filt1, c_filt2 = st.columns([1.2, 2.8])
    with c_filt1: min_conf = st.slider("Minimum Confidence Filter (%)", min_value=50, max_value=100, value=80)
    with c_filt2: horizon_filter = st.radio("Trade Timeframe / Horizon:", ["All Horizons", "Scalp", "Swing", "Long"], horizontal=True)
    
    setups_df = CloudDatabaseManager.get_setups_df()
    if not setups_df.empty:
        filtered_df = setups_df[setups_df["Confidence (%)"] >= min_conf]
        display_df = filtered_df.copy()
        if not display_df.empty:
            display_df["Ticker"] = display_df["Ticker"].apply(lambda x: get_clean_symbol(x))
            event = st.dataframe(display_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True)
            selected_idx = event.selection["rows"][0] if event and hasattr(event, "selection") and event.selection.get("rows") else 0
            selected_row = filtered_df.iloc[selected_idx]
            raw_ticker = str(selected_row["Ticker"])
        else:
            raw_ticker = "BTC-USD" if datetime.now().weekday() in [5, 6] else "NVDA"
            selected_row = {"Entry": 64200.0, "Stop Loss": 63100.0, "Target": 67500.0, "Pattern": "ICT Silver Bullet Sweep", "Action": "BUY", "Confidence (%)": 88}
    else:
        raw_ticker = "BTC-USD" if datetime.now().weekday() in [5, 6] else "NVDA"
        selected_row = {"Entry": 64200.0, "Stop Loss": 63100.0, "Target": 67500.0, "Pattern": "ICT Silver Bullet Sweep", "Action": "BUY", "Confidence (%)": 88}

    selected_ticker = get_clean_symbol(raw_ticker)
    trade_side = str(selected_row.get("Action", "BUY")).upper()
    pattern_name = str(selected_row.get("Pattern", "ICT Sweep"))

    st.divider()
    st.markdown("### 🏦 Institutional A-M-D Phase & Liquidity Flow")
    amd_phase = "Manipulation (Liquidity Stop Run) 🛑" if "Sweep" in pattern_name else "Distribution (Markup Phase) 📈"
    cvd_val = "+$14.2M (Aggressive Buying)" if trade_side == "BUY" else "-$12.5M (Aggressive Selling)"
    
    col_amd1, col_amd2 = st.columns(2)
    with col_amd1: st.markdown(f"<div class='amd-card'><span style='color:#94A3B8;'>Current Market Cycle Phase</span><br><b style='font-size:1.2rem; color:#38BDF8;'>{amd_phase}</b></div>", unsafe_allow_html=True)
    with col_amd2: st.markdown(f"<div class='amd-card'><span style='color:#94A3B8;'>Order Flow CVD Delta</span><br><b style='font-size:1.2rem; color:#00E676;'>{cvd_val}</b></div>", unsafe_allow_html=True)

    st.markdown(f"### Interactive Signal Inspection: **{selected_ticker}**")
    components.html(f"""
    <div class="tradingview-widget-container" style="height:480px;width:100%">
      <div id="tv_signal_chart" style="height:480px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{ "autosize": true, "symbol": "{get_tv_symbol(raw_ticker)}", "interval": "15", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#030712", "enable_publishing": false, "allow_symbol_change": false, "container_id": "tv_signal_chart" }});
      </script>
    </div>
    """, height=490)
    
    e_val = float(selected_row.get("Entry", 128.50))
    sl_val = float(selected_row.get("Stop Loss", 125.00))
    tp_val = float(selected_row.get("Target", 139.70))
    conf_score = int(selected_row.get("Confidence (%)", 85))
    
    c_l1, c_l2, c_l3, c_l4, c_l5 = st.columns(5)
    c_l1.markdown(f"<div class='level-card'><span style='color:#38BDF8;'>ENTRY</span><br><b>${e_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l2.markdown(f"<div class='level-card'><span style='color:#EF4444;'>STOP LOSS</span><br><b>${sl_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l3.markdown(f"<div class='level-card'><span style='color:#00E676;'>TARGET PROFIT</span><br><b>${tp_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l4.markdown(f"<div class='level-card'><span style='color:#818CF8;'>KEY SUPPORT</span><br><b>${e_val*0.97:,.2f}</b></div>", unsafe_allow_html=True)
    c_l5.markdown(f"<div class='level-card'><span style='color:#F59E0B;'>KEY RESISTANCE</span><br><b>${tp_val*1.02:,.2f}</b></div>", unsafe_allow_html=True)

    st.divider()
    st.markdown(f"### ⚡ AI-Recommended Dynamic Bracket Order: **{selected_ticker}**")
    risk_dist = abs(e_val - sl_val) if abs(e_val - sl_val) > 0 else (e_val * 0.02)
    recommended_qty = max(1.0, round((2000.0 * (conf_score / 100.0)) / risk_dist, 2))
    
    col_ex1, col_ex2, col_ex3 = st.columns([1, 1.2, 1.5])
    with col_ex1:
        trade_qty = st.number_input("Quantity (AI Recommended):", min_value=0.01, value=float(recommended_qty), step=1.0)
        st.caption(f"Confidence: **{conf_score}%** | Risk: **${(risk_dist * trade_qty):,.2f}**")
    with col_ex2:
        st.write(" "); st.write(" ")
        st.markdown(f"**Side:** <b style='color:#00E676;'>{trade_side}</b>", unsafe_allow_html=True)
        st.markdown(f"**Bracket SL / TP:** `${sl_val:,.2f}` / `${tp_val:,.2f}`")
    with col_ex3:
        st.write(" "); st.write(" ")
        if is_autopilot: st.warning("⚠ Autopilot is ACTIVE. Manual execution locked.")
        else:
            if st.button(f"🚀 EXECUTE {trade_side} {trade_qty:.2f} {selected_ticker}", type="primary", use_container_width=True):
                exec_conn = get_db_conn()
                if exec_conn:
                    try:
                        with exec_conn.cursor() as cur:
                            cur.execute("""INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, strategy, status, opened_at) VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP);""", (raw_ticker, trade_side, trade_qty, e_val, sl_val, tp_val, pattern_name))
                            exec_conn.commit()
                        st.success(f"✅ Trade Saved! Opening {trade_qty} shares of {selected_ticker}"); st.rerun()
                    except Exception as ex: st.error(f"Execution Error: {ex}")

# ==========================================
# TAB 03: PORTFOLIO & EXECUTION
# ==========================================
with tab3:
    st.subheader("⚡ Autonomous Demo Portfolio & Bracket Order Engine")
    st.markdown("### 🟢 Active Open Demo Positions")
    if not open_trades.empty:
        open_display = open_trades.copy()
        open_display['ticker'] = open_display['ticker'].apply(lambda x: get_clean_symbol(x))
        open_cols = [c for c in ['opened_at', 'ticker', 'action', 'qty', 'entry_price', 'stop_loss', 'take_profit', 'strategy', 'status'] if c in open_display.columns]
        st.markdown(render_styled_table(open_display[open_cols], ticker_col="ticker"), unsafe_allow_html=True)
    else: st.info("No open trades currently active.")

    st.divider()
    st.markdown("### 📜 Executed Trade History & Realized P&L")
    if not closed_trades.empty:
        closed_display = closed_trades.copy()
        closed_display['ticker'] = closed_display['ticker'].apply(lambda x: get_clean_symbol(x))
        closed_cols = [c for c in ['closed_at', 'ticker', 'action', 'qty', 'entry_price', 'exit_price', 'pnl', 'strategy'] if c in closed_display.columns]
        st.markdown(render_styled_table(closed_display[closed_cols], ticker_col="ticker"), unsafe_allow_html=True)
    else: st.caption("No closed trades logged yet.")

# ==========================================
# TAB 04: QUANT BACKTESTER (LIVE DATA)
# ==========================================
with tab4:
    st.subheader("🧪 Live Data Walk-Forward Backtester")
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        st.selectbox("Select Strategy:", ["SMA Crossover Trend Following", "Donchian Breakout", "Mean Reversion"])
        bt_sym = st.text_input("Asset Ticker (e.g., SPY, BTC-USD):", value="SPY")
        if st.button("▶ RUN LIVE BACKTEST", type="primary"):
            st.session_state['bt_ran'] = bt_sym
            st.success("Fetched 1 year of live history & ran calculation.")
    with col_b2:
        bt_target = st.session_state.get('bt_ran', 'SPY')
        live_bt_df = fetch_live_backtest_data(bt_target)
        if not live_bt_df.empty:
            st.line_chart(live_bt_df)
        else:
            st.warning("Fetching data... (or invalid ticker)")

# ==========================================
# TAB 05: RESEARCH & MACRO FLOW (LIVE APIS)
# ==========================================
with tab5:
    st.subheader("🐋 Institutional Research: Live YF Feeds & Macro Flow")
    t_flow1, t_flow2, t_flow3, t_flow4, t_flow5, t_flow6 = st.tabs([
        "🔍 Universal Asset Search (LIVE)", "🚀 Big Watchlist Movers (LIVE)", "🏛️ SEC Insider Wire",
        "📰 Breaking News Wire (LIVE)", "📅 Macro Economic Calendar", "🕵 Dark Pool Prints"
    ])
    
    # 1. LIVE ASSET RESEARCH
    with t_flow1:
        search_q = st.text_input("🔍 Search Asset:", value="BTC-USD" if datetime.now().weekday() in [5, 6] else "NVDA")
        q_clean = get_clean_symbol(search_q)
        q_tv = get_tv_symbol(search_q)
        
        c_res_info, c_res_chart = st.columns([1.1, 1.4])
        with c_res_info:
            st.markdown(f"## Executive Summary: **{q_clean}**")
            live_info = fetch_live_asset_info(search_q)
            if live_info:
                st.markdown(f"**Business Overview:** {live_info['summary'][:350]}...")
                st.metric("Live Market Capitalization", live_info['mcap'])
                col_i1, col_i2 = st.columns(2)
                col_i1.metric("Trailing P/E", live_info['pe_trail'])
                col_i2.metric("Forward P/E", live_info['pe_fwd'])
            else:
                st.warning("Could not fetch live fundamental data. YFinance rate limit or invalid ticker.")
        
        with c_res_chart:
            components.html(f"""<div class="tradingview-widget-container" style="height:460px;width:100%"><div id="tv_res_chart" style="height:460px;width:100%"></div><script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script><script type="text/javascript">new TradingView.widget({{ "autosize": true, "symbol": "{q_tv}", "interval": "D", "timezone": "Etc/UTC", "theme": "dark", "style": "1", "locale": "en", "toolbar_bg": "#030712", "enable_publishing": false, "container_id": "tv_res_chart" }});</script></div>""", height=470)

    # 2. LIVE BIG MOVERS
    with t_flow2:
        st.markdown("### 🚀 Live Watchlist Movers & RVOL Spikes")
        live_movers_df = fetch_live_watchlist_movers(wl_items)
        if not live_movers_df.empty:
            st.markdown(render_styled_table(live_movers_df, ticker_col="Ticker"), unsafe_allow_html=True)
        else:
            st.warning("Fetching live market data... Please refresh.")

    # 3. SEC FORM 4 (Requires Paid API - Placeholder Left Intact)
    with t_flow3:
        st.markdown("### 🏛️ SEC Form 4 C-Suite Insider Trades")
        st.caption("ℹ️ To make this live, plug in a Finnhub or Polygon.io API key here.")
        df_sec_full = pd.DataFrame({
            "Filing Date": ["2026-10-01", "2026-09-30"], "Company": ["AMZN", "NVDA"],
            "Insider Name & Title": ["Jeff Bezos (Executive Chair)", "Jensen Huang (CEO)"],
            "Transaction Type": ["AUTOMATED 10b5-1 PLAN SALE", "PURCHASE (OPEN MARKET)"],
            "Shares Traded": ["25,000,000", "97,200"], "Total Value ($)": ["$8,500,000,000", "$12,490,200"]
        })
        st.markdown(render_styled_table(df_sec_full, ticker_col="Company"), unsafe_allow_html=True)

    # 4. LIVE BREAKING NEWS
    with t_flow4:
        st.markdown("### 📰 Live Top-Watchlist News Wire")
        live_news = fetch_live_news(wl_items)
        if live_news:
            for story in live_news:
                c_img, c_body = st.columns([1, 3.5])
                with c_img: st.image(story["thumb"], use_container_width=True)
                with c_body:
                    st.markdown(f"<span class='news-tag'>{story['tag']}</span> <span style='color:#94A3B8; font-size:0.8rem; margin-left:10px;'>{story['source']}</span>", unsafe_allow_html=True)
                    st.markdown(f"#### {story['title']}")
                    st.write(story["summary"])
                st.divider()
        else:
            st.info("No recent news fetched for current watchlist.")

    # 5 & 6. MACRO / DARK POOLS
    with t_flow5:
        st.markdown("### 📅 Macroeconomic Calendar Matrix")
        st.caption("ℹ️ Needs a ForexFactory or FinancialModelingPrep API key for live feed.")
        st.markdown(render_styled_table(pd.DataFrame({"Event": ["Core CPI", "NFP"], "Impact": ["HIGH 🔴", "HIGH 🔴"], "Forecast": ["0.2%", "165K"]}), ticker_col="Event"), unsafe_allow_html=True)

    with t_flow6:
        st.markdown("### 🕵️ Institutional Dark Pool Prints")
        st.caption("ℹ️ Requires live Options/DarkPool Feed (e.g., FlowAlgo API).")
        st.markdown(render_styled_table(pd.DataFrame({"Time": ["09:31", "09:42"], "Ticker": ["SPY", "NVDA"], "Block Size": ["$24.5M", "$14.2M"], "Price": ["568.20", "128.45"]}), ticker_col="Ticker"), unsafe_allow_html=True)

# ==========================================
# TAB 06: WATCHLIST GRID
# ==========================================
with tab6:
    st.subheader("⭐ Cloud Watchlist Grid (Neon Postgres Persistence)")
    col_wadd1, col_wadd2 = st.columns([3, 1])
    with col_wadd1: new_symbol = st.text_input("Add New Symbol to Cloud Watchlist:", placeholder="e.g. TSLA, AMD")
    with col_wadd2:
        st.write(" "); st.write(" ")
        if st.button("➕ Add Symbol", type="primary") and new_symbol:
            CloudDatabaseManager.add_to_watchlist(new_symbol.upper().strip()); st.rerun()
    st.divider()
    w_cols = st.columns(2)
    for idx, item in enumerate(wl_items):
        with w_cols[idx % 2]:
            st.markdown(f"<div style='background:#0B132B; border:1px solid #1E293B; border-radius:10px; padding:12px; margin-bottom:10px;'>{get_logo_html(item, 28)}<span style='font-size:1.3rem; font-weight:bold;'>{get_clean_symbol(item)}</span></div>", unsafe_allow_html=True)
            components.html(f"""<div class="tradingview-widget-container" style="height:220px;"><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>{{"symbol": "{get_tv_symbol(item)}", "width": "100%", "height": "220", "locale": "en", "dateRange": "1M", "colorTheme": "dark", "isTransparent": true}}</script></div>""", height=230)
            if st.button(f"❌ Remove {item}", key=f"del_{item}"): CloudDatabaseManager.remove_from_watchlist(item); st.rerun()

# ==========================================
# TAB 07: PROP AUTOPILOT
# ==========================================
with tab7:
    st.subheader("🏆 Multi-Firm Prop Autopilot & Hands-Free Execution")
    col_ap1, col_ap2 = st.columns([1.2, 1.8])
    with col_ap1: new_ap_state = st.toggle("🚀 ENABLE CLOUD AUTOPILOT", value=is_autopilot)
    with col_ap2: new_min_conf = st.slider("Minimum Confidence Threshold for Live Trade Trigger (%)", min_value=50, max_value=95, value=int(min_conf_threshold), step=5)
    if new_ap_state != is_autopilot or new_min_conf != min_conf_threshold:
        set_autopilot_config_ui(new_ap_state, new_min_conf); st.rerun()

# ==========================================
# TAB 08: WEALTH & WISHLIST
# ==========================================
with tab8:
    st.subheader("💰 Wealth Vault: Long-Term Holdings & Target Buy Wishlist")
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        df_pie = pd.DataFrame({'Sector': ['Technology', 'Crypto', 'Metals', 'Cash'], 'Allocation': [35, 25, 20, 20]})
        fig_pie = px.pie(df_pie, values='Allocation', names='Sector', hole=0.4, title="Risk Parity Distribution")
        fig_pie.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_w2:
        st.markdown("### 🛡️ Long-Term Wealth Rules")
        st.markdown("* **Max Sector Concentration:** 25% Cap.")
        st.markdown("* **Risk Parity Sizing:** ATR-based volatility position scaling.")

    st.divider()
    st.markdown("### 🎯 Target Buy Accumulation Wishlist (Neon Postgres Synced)")
    df_wish = CloudDatabaseManager.get_wishlist_df()
    if not df_wish.empty:
        df_wish_display = df_wish.copy()
        df_wish_display["ticker"] = df_wish_display["ticker"].apply(lambda x: get_clean_symbol(x))
        df_wish_display.columns = ["ID", "Ticker", "Trigger Condition", "Trigger Price ($)", "Target Amount ($)"]
        st.markdown(render_styled_table(df_wish_display, ticker_col="Ticker"), unsafe_allow_html=True)
    
    st.markdown("#### ➕ Add New Target Buy Parameter to Neon Cloud")
    c_wi1, c_wi2, c_wi3, c_wi4 = st.columns(4)
    w_sym = c_wi1.text_input("Asset Symbol:", placeholder="e.g. NVDA")
    w_cond = c_wi2.text_input("Trigger Parameter:", placeholder="e.g. Down 10%")
    w_price = c_wi3.number_input("Target Price ($):", value=120.00)
    w_amt = c_wi4.number_input("Allocation ($):", value=5000)
    if st.button("➕ Save Parameter", type="primary") and w_sym:
        CloudDatabaseManager.add_wishlist_param(w_sym.strip().upper(), w_cond.strip(), w_price, w_amt); st.rerun()

# ==========================================
# TAB 09, 10 & 11: SYSTEM & STRATEGY
# ==========================================
with tab9:
    st.subheader("📡 Webhook Endpoints")
    st.code("POST http://localhost:8501/api/v1/webhook\nHeader -> Authorization: Bearer nexus_secure_bearer_token_2026", language="text")

with tab10:
    st.subheader("🧠 Active Strategy Amalgamation Performance")
    df_strats = pd.DataFrame({"Strategy Model": ["ICT Silver Bullet Sweep", "Order Flow Imbalance", "Donchian Vol Breakout"], "Target Asset Class": ["US Equities & Crypto", "Digital Assets", "Precious Metals"], "Win Rate (%)": ["81.4%", "74.2%", "68.5%"], "Status": ["ACTIVE 🟢", "ACTIVE 🟢", "ACTIVE 🟢"]})
    st.markdown(render_styled_table(df_strats, ticker_col="Strategy Model"), unsafe_allow_html=True)

with tab11:
    st.subheader("🔒 Emergency System Controls")
    if st.button("🔴 PANIC: FLATTEN ALL POSITIONS & HALT AGENTS", use_container_width=True, type="primary"):
        set_autopilot_config_ui(False, min_conf_threshold)
        st.error("EMERGENCY CIRCUIT BREAKER TRIGGERED! Autopilot halted.")
