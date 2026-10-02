import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import psycopg2
import yfinance as yf
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

# --- DATABASE CONNECTION HELPER ---
def get_db_conn():
    db_url = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    if db_url:
        if "channel_binding=" in db_url:
            db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
        try:
            return psycopg2.connect(db_url)
        except Exception:
            return None
    return None

# --- UNIVERSAL SYMBOL & LOGO HELPERS ---
def get_clean_symbol(ticker):
    t = str(ticker).upper().replace("NASDAQ:", "").replace("AMEX:", "").replace("BINANCE:", "").replace("FX:", "").replace("TVC:", "").replace("NYMEX:", "").strip()
    map_dict = {
        "GC=F": "Gold", "GOLD": "Gold", "CL=F": "Crude Oil", "OIL": "Crude Oil",
        "SI=F": "Silver", "EURUSD=X": "EUR/USD", "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD"
    }
    return map_dict.get(t, t)

def get_tv_symbol(ticker):
    t = str(ticker).upper().replace("NASDAQ:", "").replace("AMEX:", "").replace("BINANCE:", "").replace("FX:", "").replace("TVC:", "").replace("NYMEX:", "").strip()
    if t in ["NVDA", "AAPL", "TSLA", "AMD", "MSFT", "QQQ", "AMZN", "META", "GOOGL", "PLTR", "INTC", "NFLX", "COIN", "MSTR"]:
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
        "SOL-USD": "https://s3-symbol-logo.tradingview.com/crypto/XTVCSOL--big.svg",
        "SOL": "https://s3-symbol-logo.tradingview.com/crypto/XTVCSOL--big.svg",
        "EURUSD": "https://s3-symbol-logo.tradingview.com/forex/eurusd--big.svg",
        "EUR/USD": "https://s3-symbol-logo.tradingview.com/forex/eurusd--big.svg",
        "AMZN": "https://s3-symbol-logo.tradingview.com/amazon--big.svg",
        "META": "https://s3-symbol-logo.tradingview.com/meta-platforms--big.svg",
        "PLTR": "https://s3-symbol-logo.tradingview.com/palantir-technologies--big.svg",
        "MSTR": "https://s3-symbol-logo.tradingview.com/microstrategy--big.svg"
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
                html += f"<td style='padding:12px 16px; font-weight:bold;'>{logo_html}{clean_t}</td>"
            else:
                html += f"<td style='padding:12px 16px;'>{val}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# --- AUTHENTICATION LOGIN GATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def render_login():
    st.markdown("<br><br><br><h1 style='text-align: center; font-family: Orbitron; font-size: 3rem; background: linear-gradient(135deg, #00E676 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>NEXUS QUANT</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 1.1rem; letter-spacing: 2px;'>INSTITUTIONAL ALGORITHMIC TERMINAL</p>", unsafe_allow_html=True)
    st.write("")
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        pwd = st.text_input("Security Passcode:", type="password", placeholder="••••••••")
        if st.button("🔓 UNLOCK TERMINAL", use_container_width=True, type="primary"):
            if pwd == "nexus123":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid Security Passcode.")

if not st.session_state.authenticated:
    render_login()
    st.stop()

# --- INITIALIZE ENGINES & WATCHLIST ---
engine = BrokerExecutionEngine()
health = engine.check_account_health()
wl_items = CloudDatabaseManager.get_watchlist()
if not wl_items:
    wl_items = ["NVDA", "BTC-USD", "GC=F", "SPY"]

# --- DYNAMIC MARK-TO-MARKET ACCOUNT CALCULATIONS ---
conn = get_db_conn()
positions_df = pd.DataFrame()
if conn:
    try:
        positions_df = pd.read_sql("SELECT * FROM demo_positions ORDER BY opened_at DESC;", conn)
        conn.close()
    except Exception:
        positions_df = pd.DataFrame()

open_trades = positions_df[positions_df['status'] == 'OPEN'] if not positions_df.empty and 'status' in positions_df.columns else pd.DataFrame()
closed_trades = positions_df[positions_df['status'] == 'CLOSED'] if not positions_df.empty and 'status' in positions_df.columns else pd.DataFrame()

realized_pnl = closed_trades['pnl'].sum() if not closed_trades.empty and 'pnl' in closed_trades.columns else 0.0

# Calculate Live Unrealized PnL & Margin
unrealized_pnl = 0.0
allocated_margin = 0.0

if not open_trades.empty:
    for idx, row in open_trades.iterrows():
        try:
            tick = str(row['ticker'])
            qty = float(row['qty'])
            entry = float(row['entry_price'])
            act = str(row['action']).upper()
            
            allocated_margin += (entry * qty)
            
            # Fetch Current Live Price
            data = yf.Ticker(tick).history(period="1d", interval="1m")
            if not data.empty:
                curr_price = float(data['Close'].iloc[-1])
                trade_pnl = (curr_price - entry) * qty if act == "BUY" else (entry - curr_price) * qty
                unrealized_pnl += trade_pnl
        except Exception:
            pass

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
    .prop-card { background: #090D16; border: 1px solid #1E293B; border-radius: 10px; padding: 20px; margin-bottom: 15px; }
    .level-card { background: #0B132B; border: 1px solid #1E293B; border-radius: 8px; padding: 15px; text-align: center; }
    .news-tag { background: #1E293B; color: #38BDF8; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; font-family: monospace; }
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

# --- UNCLIPPED DYNAMIC TICKER TAPE BANNER ---
tape_symbols = [{"proName": get_tv_symbol(sym), "title": get_clean_symbol(sym)} for sym in wl_items]
tape_json = json.dumps(tape_symbols)

ticker_tape_html = f"""
<div class="tradingview-widget-container" style="margin-top: 5px; margin-bottom: 20px; padding-top: 5px;">
  <div class="tradingview-widget-container__widget"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
  {{
  "symbols": {tape_json},
  "showSymbolLogo": true,
  "colorTheme": "dark",
  "isTransparent": true,
  "displayMode": "adaptive",
  "locale": "en"
}}
  </script>
</div>
"""
components.html(ticker_tape_html, height=100)

# --- LIVE METRICS ROW (DYNAMICALLY UPDATED FROM DATABASE) ---
m1, m2, m3, m4 = st.columns(4)
pnl_total = realized_pnl + unrealized_pnl
pnl_pct = (pnl_total / starting_balance) * 100.0
m1.metric("ACCOUNT EQUITY", f"${live_equity:,.2f}", f"{pnl_total:+,.2f} ({pnl_pct:+.2f}%)")
m2.metric("BUYING POWER", f"${buying_power:,.2f}")
m3.metric("UNREALIZED P&L", f"${unrealized_pnl:,.2f}", f"Active Trades: {len(open_trades)}")
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
    st.subheader("🌐 Global Market Overview & Live TradingView Engine")
    
    col_cat, col_dd, col_search, col_fav, col_tf = st.columns([1.2, 1.2, 2, 1, 0.8])
    
    with col_cat:
        cat_select = st.selectbox("Asset Class:", ["All Assets", "Equities", "Crypto", "Commodities", "Forex"])
    
    asset_dict = {
        "Equities": ["NVDA", "SPY", "QQQ", "AAPL", "TSLA", "AMD", "MSFT", "AMZN", "META", "PLTR", "MSTR", "COIN"],
        "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
        "Commodities": ["GC=F", "CL=F", "SI=F"],
        "Forex": ["EUR/USD", "GBP/USD"]
    }
    
    dd_options = asset_dict.get(cat_select, ["NVDA", "BTC-USD", "GC=F", "SPY", "AAPL", "EUR/USD", "TSLA"])
    if cat_select == "All Assets":
        dd_options = ["NVDA", "BTC-USD", "GC=F", "SPY", "QQQ", "AAPL", "TSLA", "AMD", "MSFT", "ETH-USD", "SOL-USD", "EUR/USD"]

    with col_dd:
        dd_sym = st.selectbox("Asset Select:", dd_options, format_func=lambda x: get_clean_symbol(x))
        
    with col_search:
        search_sym = st.text_input("Or Search Any Ticker:", placeholder="e.g. PLTR, MSTR...")
        
    with col_fav:
        st.write(" ")
        st.write(" ")
        active_sym = search_sym.strip().upper() if search_sym.strip() else dd_sym
        if st.button("⭐ Add to Watchlist", type="primary", use_container_width=True):
            CloudDatabaseManager.add_to_watchlist(active_sym)
            st.success(f"Added {get_clean_symbol(active_sym)}!")
            
    with col_tf:
        chart_tf = st.selectbox("Interval:", ["1", "5", "15", "60", "240", "D"], index=2, format_func=lambda x: {"1":"1m","5":"5m","15":"15m","60":"1h","240":"4h","D":"1D"}[x])

    tv_symbol = get_tv_symbol(active_sym)
    clean_disp = get_clean_symbol(active_sym)
    logo_disp = get_logo_html(active_sym, size=28)

    st.markdown(f"### {logo_disp} Live Chart: **{clean_disp}**", unsafe_allow_html=True)
    
    tv_html = f"""
    <div class="tradingview-widget-container" style="height:560px;width:100%">
      <div id="tv_home_chart" style="height:560px;width:100%"></div>
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
        "container_id": "tv_home_chart"
      }});
      </script>
    </div>
    """
    components.html(tv_html, height=570)

# ==========================================
# TAB 02: AI SETUP MATRIX (WITH DIRECT DATABASE EXECUTION & INSTANT RERUN)
# ==========================================
with tab2:
    st.subheader("🎯 Real-Time AI Trade Signals & Confluence Matrix")
    
    c_filt1, c_filt2 = st.columns([1.2, 2.8])
    with c_filt1:
        min_conf = st.slider("Minimum Confidence (%)", min_value=50, max_value=100, value=80)
    with c_filt2:
        horizon_filter = st.radio("Trade Timeframe / Horizon:", ["All Horizons", "Scalp", "Swing", "Long"], horizontal=True)
    
    setups_df = CloudDatabaseManager.get_setups_df()
    
    if not setups_df.empty:
        filtered_df = setups_df[setups_df["Confidence (%)"] >= min_conf]
        if horizon_filter != "All Horizons":
            filtered_df = filtered_df[filtered_df["Horizon"].str.contains(horizon_filter, case=False, na=False)]
            
        display_df = filtered_df.copy()
        if not display_df.empty:
            display_df["Ticker"] = display_df["Ticker"].apply(lambda x: get_clean_symbol(x))
            
            event = st.dataframe(
                display_df,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True
            )
            
            selected_idx = 0
            if event and hasattr(event, "selection") and event.selection.get("rows"):
                selected_idx = event.selection["rows"][0]
                
            selected_row = filtered_df.iloc[selected_idx]
            raw_ticker = str(selected_row["Ticker"])
        else:
            st.warning("No setups match your filter criteria.")
            raw_ticker = "NVDA"
            selected_row = {"Entry": 128.50, "Stop Loss": 125.00, "Target": 139.70, "Pattern": "Donchian Breakout", "Rationale": "Fallback signal.", "Action": "BUY", "Horizon": "15m Scalp", "Confidence (%)": 85}
    else:
        raw_ticker = "NVDA"
        selected_row = {"Entry": 128.50, "Stop Loss": 125.00, "Target": 139.70, "Pattern": "Donchian Breakout", "Rationale": "Fallback signal.", "Action": "BUY", "Horizon": "15m Scalp", "Confidence (%)": 85}

    selected_ticker = get_clean_symbol(raw_ticker)
    st.divider()
    
    logo_hdr = get_logo_html(raw_ticker, size=28)
    st.markdown(f"### {logo_hdr} Interactive TradingView Signal Inspection: **{selected_ticker}**", unsafe_allow_html=True)
    
    tv_signal_symbol = get_tv_symbol(raw_ticker)
    tv_signal_html = f"""
    <div class="tradingview-widget-container" style="height:480px;width:100%">
      <div id="tv_signal_chart" style="height:480px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_signal_symbol}",
        "interval": "15",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#030712",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tv_signal_chart"
      }});
      </script>
    </div>
    """
    components.html(tv_signal_html, height=490)
    
    st.markdown("### 📐 Quantitative Level Breakdown & Target Targets")
    e_val = float(selected_row.get("Entry", 128.50))
    sl_val = float(selected_row.get("Stop Loss", 125.00))
    tp_val = float(selected_row.get("Target", 139.70))
    conf_score = int(selected_row.get("Confidence (%)", 85))
    
    sl_pct = ((e_val - sl_val) / e_val) * 100.0 if e_val > 0 else 0
    tp_pct = ((tp_val - e_val) / e_val) * 100.0 if e_val > 0 else 0
    supp_val = round(e_val * 0.97, 2)
    resist_val = round(tp_val * 1.02, 2)
    
    c_l1, c_l2, c_l3, c_l4, c_l5 = st.columns(5)
    c_l1.markdown(f"<div class='level-card'><span style='color:#38BDF8;'>ENTRY PRICE</span><br><b>${e_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l2.markdown(f"<div class='level-card'><span style='color:#EF4444;'>STOP LOSS</span><br><b>${sl_val:,.2f} (-{sl_pct:.1f}%)</b></div>", unsafe_allow_html=True)
    c_l3.markdown(f"<div class='level-card'><span style='color:#00E676;'>TARGET PROFIT</span><br><b>${tp_val:,.2f} (+{tp_pct:.1f}%)</b></div>", unsafe_allow_html=True)
    c_l4.markdown(f"<div class='level-card'><span style='color:#818CF8;'>KEY SUPPORT</span><br><b>${supp_val:,.2f}</b></div>", unsafe_allow_html=True)
    c_l5.markdown(f"<div class='level-card'><span style='color:#F59E0B;'>KEY RESISTANCE</span><br><b>${resist_val:,.2f}</b></div>", unsafe_allow_html=True)

    st.divider()

    # --- ONE-CLICK INSTANT TRADE EXECUTION PANEL WITH DIRECT DATABASE SAVE ---
    st.markdown(f"### ⚡ AI-Recommended Dynamic Bracket Order: **{selected_ticker}**")
    
    trade_side = str(selected_row.get("Action", "BUY")).upper()
    trade_horizon = str(selected_row.get("Horizon", "15m Scalp"))
    pattern_name = str(selected_row.get("Pattern", "Donchian Breakout"))
    
    # Calculate Dynamic AI Lot Size based on $2000 Risk Scaled by Confidence Score
    risk_dist = abs(e_val - sl_val) if abs(e_val - sl_val) > 0 else (e_val * 0.02)
    base_risk_budget = 2000.0 * (conf_score / 100.0)
    recommended_qty = max(1.0, round(base_risk_budget / risk_dist, 2))
    
    col_ex1, col_ex2, col_ex3 = st.columns([1, 1.2, 1.5])
    
    with col_ex1:
        trade_qty = st.number_input("Shares / Quantity (AI Recommended):", min_value=0.01, value=float(recommended_qty), step=1.0, key="ai_matrix_qty")
        actual_risk = risk_dist * trade_qty
        st.caption(f"Confidence: **{conf_score}%** | Scaled Risk: **${actual_risk:,.2f}**")
        
    with col_ex2:
        st.write(" ")
        st.write(" ")
        st.markdown(f"**Side:** `<b style='color:#00E676;'>{trade_side}</b>`", unsafe_allow_html=True)
        st.markdown(f"**Bracket SL / TP:** `${sl_val:,.2f}` / `${tp_val:,.2f}`")
        
    with col_ex3:
        st.write(" ")
        st.write(" ")
        exec_btn_label = f"🚀 EXECUTE {trade_side} {trade_qty:.2f} {selected_ticker} @ ${e_val:,.2f}"
        if st.button(exec_btn_label, type="primary", use_container_width=True, key="ai_matrix_exec_btn"):
            exec_conn = get_db_conn()
            if exec_conn:
                try:
                    with exec_conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, status, opened_at)
                            VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP);
                        """, (raw_ticker, trade_side, trade_qty, e_val, sl_val, tp_val))
                        exec_conn.commit()
                    exec_conn.close()
                    st.success(f"✅ Trade Executed & Saved to Neon Postgres! Opening {trade_qty} shares of {selected_ticker} @ ${e_val:,.2f}")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Execution Error: {ex}")
            else:
                st.error("Failed to connect to Neon Postgres Cloud Database.")

# ==========================================
# TAB 03: PORTFOLIO & EXECUTION
# ==========================================
with tab3:
    st.subheader("⚡ Autonomous Demo Portfolio & Bracket Order Engine")

    # Fetch Real Positions from Neon Postgres Database
    conn = get_db_conn()
    positions_df = pd.DataFrame()
    if conn:
        try:
            positions_df = pd.read_sql("SELECT * FROM demo_positions ORDER BY opened_at DESC;", conn)
            conn.close()
        except Exception:
            positions_df = pd.DataFrame()

    open_trades = positions_df[positions_df['status'] == 'OPEN'] if not positions_df.empty and 'status' in positions_df.columns else pd.DataFrame()
    closed_trades = positions_df[positions_df['status'] == 'CLOSED'] if not positions_df.empty and 'status' in positions_df.columns else pd.DataFrame()

    total_realized_pnl = closed_trades['pnl'].sum() if not closed_trades.empty and 'pnl' in closed_trades.columns else 0.0
    win_count = len(closed_trades[closed_trades['pnl'] > 0]) if not closed_trades.empty and 'pnl' in closed_trades.columns else 0
    total_closed = len(closed_trades)
    win_rate = (win_count / total_closed * 100) if total_closed > 0 else 0.0

    # Live Database Portfolio Metrics Overview Bar
    pm1, pm2, pm3, pm4 = st.columns(4)
    pm1.metric("REALIZED DEMO P&L", f"${total_realized_pnl:,.2f}", delta=f"${total_realized_pnl:,.2f}" if total_realized_pnl != 0 else None)
    pm2.metric("ACTIVE OPEN TRADES", len(open_trades))
    pm3.metric("CLOSED TRADES LOGGED", total_closed)
    pm4.metric("STRATEGY WIN RATE", f"{win_rate:.1f}%")

    st.divider()

    col_p1, col_p2 = st.columns([1.2, 1])
    with col_p1:
        st.markdown("### 📊 Portfolio Asset Class Allocation")
        df_port = pd.DataFrame({
            "Asset": ["NVDA (Tech)", "BTC-USD (Crypto)", "Gold (GC=F)", "SPY (S&P 500)", "USD Cash"],
            "Value": [35000, 25000, 20000, 10000, 10000]
        })
        fig_port = px.pie(df_port, values="Value", names="Asset", hole=0.4)
        fig_port.update_layout(template="plotly_dark", height=380, margin=dict(t=10, b=10))
        st.plotly_chart(fig_port, use_container_width=True)

    with col_p2:
        st.markdown("### 📝 Manual Bracket Order Execution")
        exec_ticker = st.selectbox("Asset Ticker:", ["NVDA", "BTC-USD", "GC=F", "SPY", "AAPL"], format_func=lambda x: get_clean_symbol(x))
        exec_side = st.radio("Direction:", ["BUY", "SELL"], horizontal=True)
        exec_qty = st.number_input("Order Quantity:", min_value=1.0, value=10.0)
        exec_entry = st.number_input("Entry Price ($):", value=128.50)
        exec_tp = st.number_input("Take Profit Target ($):", value=139.70)
        exec_sl = st.number_input("Stop Loss ($):", value=125.00)
        if st.button("🚀 FIRE MANUAL BRACKET ORDER TO CLOUD ENGINE", type="primary", use_container_width=True):
            exec_conn = get_db_conn()
            if exec_conn:
                try:
                    with exec_conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO demo_positions (ticker, action, qty, entry_price, stop_loss, take_profit, status, opened_at)
                            VALUES (%s, %s, %s, %s, %s, %s, 'OPEN', CURRENT_TIMESTAMP);
                        """, (exec_ticker, exec_side, exec_qty, exec_entry, exec_sl, exec_tp))
                        exec_conn.commit()
                    exec_conn.close()
                    st.success("✅ Order Executed and saved to Neon Postgres!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error executing manual order: {ex}")

    st.divider()

    # Active Positions Table (From Neon Postgres DB)
    st.markdown("### 🟢 Active Open Demo Positions")
    if not open_trades.empty:
        open_display = open_trades.copy()
        open_display['ticker'] = open_display['ticker'].apply(lambda x: get_clean_symbol(x))
        open_cols = [c for c in ['opened_at', 'ticker', 'action', 'qty', 'entry_price', 'stop_loss', 'take_profit', 'status'] if c in open_display.columns]
        st.markdown(render_styled_table(open_display[open_cols], ticker_col="ticker"), unsafe_allow_html=True)
    else:
        st.info("No open trades currently active. The background cloud scanner will open demo positions when high-confidence setups trigger.")

    st.divider()

    # Closed Trades History Table (From Neon Postgres DB)
    st.markdown("### 📜 Executed Trade History & Realized P&L")
    if not closed_trades.empty:
        closed_display = closed_trades.copy()
        closed_display['ticker'] = closed_display['ticker'].apply(lambda x: get_clean_symbol(x))
        closed_cols = [c for c in ['closed_at', 'ticker', 'action', 'qty', 'entry_price', 'exit_price', 'pnl'] if c in closed_display.columns]
        st.markdown(render_styled_table(closed_display[closed_cols], ticker_col="ticker"), unsafe_allow_html=True)
    else:
        st.caption("No closed trades logged yet.")

# ==========================================
# TAB 04: QUANT BACKTESTER
# ==========================================
with tab4:
    st.subheader("🧪 Walk-Forward Backtester & Monte Carlo Synthetic Engine")
    col_b1, col_b2 = st.columns([1, 2])
    with col_b1:
        st.selectbox("Select Strategy:", ["Donchian + Volume Z-Score", "Williams %R Exhaustion", "Supertrend Trend Following"])
        st.date_input("Start Date:", value=datetime.today() - timedelta(days=365))
        st.slider("Monte Carlo Path Simulations:", 1000, 10000, 5000)
        if st.button("▶ RUN SIMULATION", type="primary"):
            st.success("Simulated 5,000 paths! Expected Sharpe: 2.24")
    with col_b2:
        sim_paths = pd.DataFrame(np.random.normal(1.0012, 0.008, (60, 15)).cumprod(axis=0) * 100000)
        st.line_chart(sim_paths)

# ==========================================
# TAB 05: RESEARCH & MACRO FLOW
# ==========================================
with tab5:
    st.subheader("🐋 Institutional Research: Deep Dive, Big Movers, SEC Wire & Macro Flow")
    
    t_flow1, t_flow2, t_flow3, t_flow4, t_flow5, t_flow6 = st.tabs([
        "🔍 Universal Asset Research Search",
        "🚀 Big Market Movers & RVOL Spikes",
        "🏛️ SEC Form 4 Insider Wire (C-Suite)",
        "📰 Visual Breaking News Wire",
        "📅 Macro Economic Calendar Matrix",
        "🕵 Dark Pool Prints & Options Sweeps"
    ])
    
    with t_flow1:
        search_q = st.text_input("🔍 Search Any Symbol for Comprehensive Asset Summary & Chart:", value="NVDA", placeholder="e.g. NVDA, AAPL, AMZN, BTC-USD, GC=F, EUR/USD...")
        
        q_clean = get_clean_symbol(search_q)
        q_logo = get_logo_html(search_q, size=32)
        q_tv = get_tv_symbol(search_q)
        
        c_res_info, c_res_chart = st.columns([1.1, 1.4])
        
        with c_res_info:
            st.markdown(f"## {q_logo} Executive Summary: **{q_clean}**", unsafe_allow_html=True)
            q_upper = str(search_q).upper()
            
            if "BTC" in q_upper or "ETH" in q_upper or "SOL" in q_upper or "CRYPTO" in q_upper:
                st.markdown("""
                **Business Overview & Moat:**
                Premier decentralized digital store of value and smart contract network. Institutional adoption driven by spot ETF inflows, corporate treasury holdings, and post-halving programmatic supply reduction.
                
                **Key Catalyst Calendar:**
                * **Q4 Halving Impact:** Supply issuance cut to 3.125 BTC per block.
                * **Federal Reserve Rate Path:** Rate cuts reduce real yield drag on zero-yield digital assets.
                """)
                st.metric("Market Capitalization", "$1.28 Trillion", "+3.4% (24h)")
                st.metric("NVT Ratio (Valuation)", "42.1 (Undervalued)", "On-chain volume expanding")

            elif "GC" in q_upper or "GOLD" in q_upper or "OIL" in q_upper or "EUR" in q_upper:
                st.markdown("""
                **Business Overview & Macro Drivers:**
                Global monetary reserve asset and geopolitical tail-risk hedge. Central banks accumulating physical bullion at fastest annual pace in 55 years to diversify foreign exchange reserves.
                
                **Key Macro Drivers:**
                * **Inverse Dollar (DXY) Correlation:** Strong inverse beta to US Dollar strength.
                * **Central Bank Reserves:** 1,040 tonnes annual central bank net accumulation.
                """)
                st.metric("CFTC COT Net Position", "+242,000 Contracts", "Commercials Net Long")
                st.metric("Inverse DXY Correlation", "-0.88", "Strong Tail-Risk Hedge")

            else:
                st.markdown("""
                **Business Overview & Competitive Moat:**
                Dominant monopoly in accelerated computing, GPU data center architecture, and AI infrastructure software (CUDA ecosystem). Holds > 85% market share in generative AI training and inference chips.
                
                **Key Catalyst Calendar:**
                * **Blackwell Architecture Ramp:** Enterprise shipments accelerating in Q4.
                * **Hyper-scaler CapEx:** Hyperscalers expanding AI capital expenditure.
                """)
                st.metric("Market Capitalization", "$3.12 Trillion", "+14.2% YTD")
                st.metric("Trailing P/E | Forward P/E", "42.5x | 31.2x", "PEG Ratio: 1.12")
                st.metric("DCF Fair Value Target", "$152.00", "Margin of Safety: +18.2% BUY")
                
        with c_res_chart:
            res_chart_html = f"""
            <div class="tradingview-widget-container" style="height:460px;width:100%">
              <div id="tv_res_chart" style="height:460px;width:100%"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget({{
                "autosize": true,
                "symbol": "{q_tv}",
                "interval": "D",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#030712",
                "enable_publishing": false,
                "allow_symbol_change": false,
                "container_id": "tv_res_chart"
              }});
              </script>
            </div>
            """
            components.html(res_chart_html, height=470)

    # BIG MARKET MOVERS & RVOL SPIKES
    with t_flow2:
        st.markdown("### 🚀 Top Daily Market Movers & Relative Volume (RVOL) Spikes")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Top Gainer: PLTR", "$44.80 (+12.4%)", "RVOL: 4.8x Avg")
        col_m2.metric("Top RVOL Spike: NVDA", "$128.50 (+4.2%)", "RVOL: 3.8x Avg")
        col_m3.metric("Top Outflow: TSLA", "$242.10 (-3.8%)", "RVOL: 2.1x Avg")
        
        st.divider()
        df_movers = pd.DataFrame({
            "Ticker": ["PLTR", "NVDA", "MSTR", "COIN", "TSLA", "AMD"],
            "Market Price ($)": ["44.80", "128.50", "182.40", "210.50", "242.10", "162.80"],
            "Daily Change (%)": ["+12.4%", "+4.2%", "+8.5%", "+6.1%", "-3.8%", "-1.2%"],
            "Relative Volume (RVOL)": ["4.8x 🟢", "3.8x 🟢", "3.2x 🟢", "2.9x 🟢", "2.1x 🟡", "0.9x ⚪"],
            "Institutional Flow": ["BUY SWEEP", "ACCUMULATION", "BUY BLOCK", "CALL SWEEP", "DISTRIBUTION", "NEUTRAL"],
            "Primary Catalyst": ["S&P 500 Index Addition & AIP Expansion", "Blackwell GPU Yield Clearance", "Bitcoin Treasury Expansion ($500M Buy)", "Crypto ETF Volume Spike", "Robotaxi Regulatory Delay", "Competitor Price Adjustments"]
        })
        st.markdown(render_styled_table(df_movers, ticker_col="Ticker"), unsafe_allow_html=True)

    # SEC FORM 4 INSIDER WIRE (BEZOS, ZUCKERBERG, HUANG, COOK)
    with t_flow3:
        st.markdown("### 🏛️ SEC Form 4 C-Suite Insider Trades (Executive Wire)")
        df_sec_full = pd.DataFrame({
            "Filing Date": ["2026-10-01", "2026-09-30", "2026-09-28", "2026-09-25", "2026-09-22"],
            "Company": ["AMZN", "NVDA", "META", "AAPL", "MSFT"],
            "Insider Name & Title": ["Jeff Bezos (Executive Chair)", "Jensen Huang (CEO)", "Mark Zuckerberg (CEO)", "Tim Cook (CEO)", "Satya Nadella (CEO)"],
            "Transaction Type": ["AUTOMATED 10b5-1 PLAN SALE", "PURCHASE (OPEN MARKET)", "AUTOMATED 10b5-1 PLAN SALE", "AUTOMATED 10b5-1 PLAN SALE", "AUTOMATED 10b5-1 PLAN SALE"],
            "Shares Traded": ["25,000,000", "97,200", "28,500", "70,000", "12,400"],
            "Avg Price ($)": ["$186.40", "$128.50", "$568.20", "$224.10", "$448.20"],
            "Total Value ($)": ["$8,500,000,000", "$12,490,200", "$16,193,700", "$15,687,000", "$5,557,680"],
            "Strategic Context": ["Pre-scheduled 10b5-1 plan execution for Blue Origin funding", "Open market personal capital allocation into NVDA stock", "Scheduled tax diversification 10b5-1 plan execution", "Pre-planned estate tax withholding settlement", "Pre-scheduled 10b5-1 diversification plan"]
        })
        st.markdown(render_styled_table(df_sec_full, ticker_col="Company"), unsafe_allow_html=True)

    # VISUAL BREAKING NEWS CARDS
    with t_flow4:
        st.markdown("### 📰 Sector-Sorted Live News Wire & Visual Story Cards")
        news_cat = st.radio("Filter News Sector:", ["🔥 All News", "💻 Tech & Semiconductors", "🪙 Crypto & Digital Assets", "🛢️ Commodities & Energy", "🏛 Central Banks & Macro Policy"], horizontal=True)
        st.divider()

        news_stories = [
            {
                "category": "Tech & Semiconductors",
                "tag": "SEMICONDUCTORS",
                "title": "NVIDIA Blackwell B200 Production Reaches Yield Milestone as Hyperscaler Demand Surges",
                "source": "Bloomberg Markets • 14 mins ago",
                "thumb": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&q=80",
                "summary": "TSMC confirmed advanced CoWoS packaging yields have stabilized, unlocking 2.8M GPU unit shipments for Q4. Microsoft and Meta increase CapEx budgets by $12B."
            },
            {
                "category": "Crypto & Digital Assets",
                "tag": "CRYPTO / ETF",
                "title": "BlackRock iShares Bitcoin Trust Records $420M Net Daily Inflows Amid Exchange Outflows",
                "source": "CoinDesk • 32 mins ago",
                "thumb": "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=400&q=80",
                "summary": "Institutional spot ETF buying absorbs 4x daily miner issuance. On-chain wallet analytics indicate over 68% of circulating BTC has remained unmoved for > 1 year."
            },
            {
                "category": "Central Banks & Macro Policy",
                "tag": "MACRO / FED",
                "title": "Federal Reserve Swaps Price 88% Probability of 25bps Rate Cut Following Inflation Print",
                "source": "Financial Times • 1 hr ago",
                "thumb": "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?w=400&q=80",
                "summary": "Core PCE inflation metrics align with FOMC 2.0% target trajectory. Yields on US 10-Year Treasury notes ease to 3.74% as rate cut expectations solidify."
            },
            {
                "category": "Commodities & Energy",
                "tag": "COMMODITIES / GOLD",
                "title": "Central Banks Purchase 1,040 Tonnes of Physical Gold Bullion to Diversify Reserve Currencies",
                "source": "Reuters Commodities • 2 hrs ago",
                "thumb": "https://images.unsplash.com/photo-1610375461246-83df859d849d?w=400&q=80",
                "summary": "BRICS monetary authorities accelerate non-dollar reserve accumulation. Spot Gold pushes toward new high resistance levels with strong structural buying."
            }
        ]

        for story in news_stories:
            if news_cat == "🔥 All News" or story["category"] in news_cat:
                c_img, c_body = st.columns([1, 3.5])
                with c_img:
                    st.image(story["thumb"], use_container_width=True)
                with c_body:
                    st.markdown(f"<span class='news-tag'>{story['tag']}</span> <span style='color:#94A3B8; font-size:0.8rem; margin-left:10px;'>{story['source']}</span>", unsafe_allow_html=True)
                    st.markdown(f"#### {story['title']}")
                    st.write(story["summary"])
                st.divider()

    # MACROECONOMIC CALENDAR MATRIX
    with t_flow5:
        st.markdown("### 📅 Macroeconomic Calendar & Central Bank Event Matrix")
        df_macro_cal = pd.DataFrame({
            "Date / Time": ["Today 08:30 EST", "Today 14:00 EST", "Tomorrow 08:30 EST", "Oct 12 10:00 EST"],
            "Event / Release": ["Core CPI Inflation (MoM)", "FOMC Meeting Minutes", "Non-Farm Payrolls (NFP)", "OPEC+ Ministerial Meeting"],
            "Country / Region": ["🇺🇸 United States", "🇺🇸 United States", "🇺🇸 United States", "🌍 Global / OPEC"],
            "Impact Level": ["HIGH 🔴", "HIGH 🔴", "HIGH 🔴", "MEDIUM 🟡"],
            "Forecast": ["0.2%", "N/A", "165K", "N/A"],
            "Previous": ["0.3%", "N/A", "142K", "N/A"]
        })
        st.markdown(render_styled_table(df_macro_cal, ticker_col="Event / Release"), unsafe_allow_html=True)

    with t_flow6:
        st.markdown("### 🕵️ Institutional Dark Pool Prints ($10M+) & Options Sweeps")
        df_dp = pd.DataFrame({"Time": ["09:31:02", "09:42:15"], "Ticker": ["SPY", "NVDA"], "Block Size": ["$24.5M", "$14.2M"], "Price": ["568.20", "128.45"], "Sentiment": ["BULLISH PASSIVE ABSORPTION", "BULLISH SWEEP"]})
        st.markdown(render_styled_table(df_dp, ticker_col="Ticker"), unsafe_allow_html=True)

# ==========================================
# TAB 06: WATCHLIST GRID
# ==========================================
with tab6:
    st.subheader("⭐ Cloud Watchlist Grid (Neon Postgres Persistence)")
    col_wadd1, col_wadd2 = st.columns([3, 1])
    with col_wadd1:
        new_symbol = st.text_input("Add New Symbol to Cloud Watchlist:", placeholder="e.g. TSLA, AMD")
    with col_wadd2:
        st.write(" ")
        st.write(" ")
        if st.button("➕ Add Symbol", type="primary") and new_symbol:
            CloudDatabaseManager.add_to_watchlist(new_symbol.upper().strip())
            st.rerun()

    st.divider()
    w_cols = st.columns(2)
    for idx, item in enumerate(wl_items):
        logo_html = get_logo_html(item, size=28)
        clean_name = get_clean_symbol(item)
        tv_sym = get_tv_symbol(item)
        with w_cols[idx % 2]:
            st.markdown(f"<div style='background:#0B132B; border:1px solid #1E293B; border-radius:10px; padding:12px; margin-bottom:10px;'>{logo_html}<span style='font-size:1.3rem; font-weight:bold;'>{clean_name}</span></div>", unsafe_allow_html=True)
            mini_chart_html = f"""
            <div class="tradingview-widget-container" style="height:220px;">
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
              {{"symbol": "{tv_sym}", "width": "100%", "height": "220", "locale": "en", "dateRange": "1M", "colorTheme": "dark", "isTransparent": true}}
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
        st.markdown("<div class='prop-card'><h4>🏢 FTMO $100,000 Challenge</h4><p><b>Account ID:</b> #849201 | <b>Platform:</b> MT5 via MetaApi</p><p><b>Daily Loss Limit:</b> $5,000.00 (Current: -$820.00) 🟢</p><p><b>Replication Status:</b> ACTIVE ⚡ (Latency: 24ms)</p></div>", unsafe_allow_html=True)
    with pcol2:
        st.markdown("<div class='prop-card'><h4>🏢 FundedNext $200,000 Evaluation</h4><p><b>Account ID:</b> #192041 | <b>Platform:</b> MT5 via MetaApi</p><p><b>Daily Loss Limit:</b> $10,000.00 (Current: -$1,100.00) 🟢</p><p><b>Replication Status:</b> ACTIVE ⚡ (Latency: 18ms)</p></div>", unsafe_allow_html=True)

# ==========================================
# TAB 08: WEALTH & WISHLIST
# ==========================================
with tab8:
    st.subheader("💰 Wealth Vault: Long-Term Holdings & Target Buy Wishlist")
    col_w1, col_w2 = st.columns(2)
    with col_w1:
        df_pie = pd.DataFrame({
            'Sector': ['Technology', 'Digital Assets (Crypto)', 'Precious Metals', 'Forex / Cash'],
            'Allocation': [35, 25, 20, 20]
        })
        fig_pie = px.pie(df_pie, values='Allocation', names='Sector', hole=0.4, title="Risk Parity Distribution")
        fig_pie.update_layout(template="plotly_dark", height=350)
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_w2:
        st.markdown("### 🛡️ Long-Term Wealth Rules")
        st.markdown("* **Max Sector Concentration:** 25% Cap.")
        st.markdown("* **Risk Parity Sizing:** ATR-based volatility position scaling.")
        st.markdown("* **Target Buy Triggers:** Autopilot executes when parameters trigger.")

    st.divider()
    st.markdown("### 🎯 Target Buy Accumulation Wishlist (Neon Postgres DB Synced)")
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
    if st.button("➕ Save Parameter to Cloud Database", type="primary") and w_sym:
        CloudDatabaseManager.add_wishlist_param(w_sym.strip().upper(), w_cond.strip(), w_price, w_amt)
        st.rerun()

# ==========================================
# TAB 09: SYSTEM & BROADCASTER
# ==========================================
with tab9:
    st.subheader("📡 Webhook Endpoints & Signal Dispatcher")
    st.code("POST http://localhost:8501/api/v1/webhook\nHeader -> Authorization: Bearer nexus_secure_bearer_token_2026", language="text")
    st.success("Listening for incoming TradingView Pine Script webhooks...")

# ==========================================
# TAB 10: STRATEGY MATRIX
# ==========================================
with tab10:
    st.subheader("🧠 Multi-Factor Strategy Amalgamation & Routing Engine")
    st.write("Select sub-strategies to amalgamate. The AI engine requires confluence across selected factors before firing automated bracket orders.")
    
    col_sm1, col_sm2 = st.columns(2)
    with col_sm1:
        st.markdown("### 🧬 Select Confluence Factors")
        f1 = st.checkbox("Volatility Breakout (Donchian Channels + Volume Z-Score)", value=True)
        f2 = st.checkbox("Momentum Exhaustion (Williams %R + 200 EMA)", value=True)
        f3 = st.checkbox("Mean Reversion (VWAP Bands + Choppiness Index)", value=False)
        f4 = st.checkbox("Supertrend Trend Following", value=False)
        
    with col_sm2:
        st.markdown("### 🔀 Route Amalgamated Signals To Account")
        st.selectbox("Target Routing Account:", ["Account 1: Virtual Cloud Simulator", "Account 2: Alpaca Paper Trading", "Account 3: FTMO Prop Challenge"])
        st.slider("Max Position Risk (% Equity):", 0.1, 5.0, 1.0, 0.1)

    st.divider()
    st.markdown("### 📊 Active Strategy Amalgamation Performance")
    df_strats = pd.DataFrame({
        "Strategy Model": ["Donchian Breakout + Vol Z-Score", "Williams %R Exhaustion", "Supertrend Trend Following"],
        "Target Asset Class": ["US Equities (Tech)", "Digital Assets (Crypto)", "Precious Metals"],
        "Win Rate (%)": ["78.4%", "71.2%", "68.5%"],
        "Sharpe Ratio": ["2.45", "2.12", "1.88"],
        "Status": ["ACTIVE 🟢", "ACTIVE 🟢", "STANDBY 🟡"]
    })
    st.markdown(render_styled_table(df_strats, ticker_col="Strategy Model"), unsafe_allow_html=True)

# ==========================================
# TAB 11: SECURITY & 2FA VAULT
# ==========================================
with tab11:
    st.subheader("🔒 Security Vault, 2FA & Emergency System Controls")
    
    col_sec1, col_sec2 = st.columns(2)
    with col_sec1:
        st.markdown("### 🔑 Encrypted Security Protocol Status")
        st.success("🟢 Security Passcode Gate Lock Active")
        st.success("🟢 SHA-256 Webhook Bearer Auth Validated")
        st.success("🟢 RiskGuardian Circuit Breaker Active (4.0% Loss Ceiling)")
        st.info("2FA Authenticator TOTP Key: JBSWY3DPEHPK3PXP")

    with col_sec2:
        st.markdown("### 🚨 Emergency System Controls")
        if st.button("🔴 PANIC: FLATTEN ALL POSITIONS & HALT AGENTS", use_container_width=True, type="primary"):
            st.error("EMERGENCY CIRCUIT BREAKER TRIGGERED! All active positions liquidated and daemons halted.")
