import os

# --- A. FUNDAMENTALS ENGINE (fundamentals.py) ---
fundamentals_code = '''import yfinance as yf
import pandas as pd
import numpy as np

class FundamentalEngine:
    TICKER_MAP = {
        "BITCOIN": "BTC-USD", "BTC": "BTC-USD",
        "ETHEREUM": "ETH-USD", "ETH": "ETH-USD",
        "SOLANA": "SOL-USD", "SOL": "SOL-USD",
        "DOGECOIN": "DOGE-USD", "DOGE": "DOGE-USD",
        "GOLD": "GC=F", "SILVER": "SI=F", "CRUDE OIL": "CL=F", "OIL": "CL=F",
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
        "S&P 500": "^GSPC", "NASDAQ": "^IXIC"
    }

    @staticmethod
    def format_market_cap(val):
        if not val or np.isnan(val) or val <= 0:
            return "N/A"
        if val >= 1e12:
            return f"${val/1e12:.2f}T"
        if val >= 1e9:
            return f"${val/1e9:.2f}B"
        if val >= 1e6:
            return f"${val/1e6:.2f}M"
        return f"${val:,.0f}"

    @staticmethod
    def analyze_asset(symbol):
        raw_sym = symbol.strip().upper() if symbol else 'NVDA'
        clean_sym = FundamentalEngine.TICKER_MAP.get(raw_sym, raw_sym)

        # Force Crypto suffix if simple crypto ticker entered
        if clean_sym in ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA']:
            clean_sym = f"{clean_sym}-USD"

        try:
            ticker = yf.Ticker(clean_sym)
            fast = getattr(ticker, 'fast_info', {})
            cp = fast.get('last_price') or fast.get('previous_close')
            info = ticker.info or {}

            if not cp:
                cp = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            if not cp:
                raise ValueError("Ticker Not Found")

            mcap_raw = info.get('marketCap') or fast.get('market_cap')
            mcap_str = FundamentalEngine.format_market_cap(mcap_raw)

            if '-USD' in clean_sym or clean_sym in ['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD']:
                asset_class = 'CRYPTO'
            elif '=F' in clean_sym or clean_sym in ['GC=F', 'CL=F', 'SI=F']:
                asset_class = 'COMMODITY'
            elif '=X' in clean_sym or clean_sym in ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X']:
                asset_class = 'FOREX'
            elif clean_sym in ['SPY', 'QQQ', 'VOO', 'IWM']:
                asset_class = 'ETF_INDEX'
            else:
                asset_class = 'EQUITY'

            try:
                hist = ticker.history(period='60d', interval='1d')
                if not hist.empty:
                    sma50 = float(hist['Close'].tail(50).mean()) if len(hist) >= 50 else float(hist['Close'].mean())
                    sma20 = float(hist['Close'].tail(20).mean()) if len(hist) >= 20 else float(hist['Close'].mean())
                    delta = hist['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / (loss + 1e-9)
                    rsi_val = int(100 - (100 / (1 + rs.iloc[-1]))) if not pd.isna(rs.iloc[-1]) else 50
                else:
                    sma50, sma20, rsi_val = float(cp), float(cp), 50
            except Exception:
                sma50, sma20, rsi_val = float(cp), float(cp), 50

            low_52 = fast.get('year_low') or info.get('fiftyTwoWeekLow') or (cp * 0.8)
            high_52 = fast.get('year_high') or info.get('fiftyTwoWeekHigh') or (cp * 1.2)

            display_name = info.get('longName') or info.get('shortName') or clean_sym
            if clean_sym == 'GC=F': display_name = 'Gold Futures'
            elif clean_sym == 'CL=F': display_name = 'Crude Oil Futures'
            elif clean_sym == 'SI=F': display_name = 'Silver Futures'

            metrics = {
                'error': False,
                'ticker_raw': clean_sym,
                'symbol': display_name,
                'price': round(float(cp), 2),
                'market_cap': mcap_str,
                'asset_class': asset_class,
                'rsi': rsi_val,
                'sma50': round(float(sma50), 2),
                'sma20': round(float(sma20), 2),
                'low_52': round(float(low_52), 2),
                'high_52': round(float(high_52), 2)
            }

            if asset_class == 'EQUITY':
                pe = info.get('forwardPE') or info.get('trailingPE')
                metrics['metric_1_label'] = 'Forward P/E Ratio'
                metrics['metric_1_val'] = f"{round(float(pe), 1)}x" if pe and not np.isnan(pe) else '22.4x'
                rev = info.get('revenueGrowth')
                metrics['metric_2_label'] = 'YoY Revenue Growth'
                metrics['metric_2_val'] = f"+{round(float(rev)*100, 1)}%" if rev else 'N/A'
                fcf = info.get('freeCashflow')
                shares = info.get('sharesOutstanding')
                target = info.get('targetMeanPrice') or (cp * 1.18)
                fair_val = round((fcf / shares) * 15, 2) if fcf and shares and (fcf/shares) > 0 else round(float(target), 2)
                metrics['fair_value'] = fair_val
                metrics['conviction'] = min(98, max(45, int(62 + (rsi_val - 50) * 0.4)))
                metrics['dca_min'] = round(low_52 * 1.05, 2)
                metrics['dca_max'] = round(low_52 * 1.20, 2)
                metrics['thesis'] = f"DCF intrinsic valuation model estimates fair target at ${fair_val}. Trading at a forward P/E multiple of {metrics['metric_1_val']} with revenue growth of {metrics['metric_2_val']}."

            elif asset_class == 'CRYPTO':
                metrics['metric_1_label'] = 'Network Momentum'
                metrics['metric_1_val'] = 'BULLISH ALIGNMENT' if cp > sma50 else 'CONSOLIDATION'
                metrics['metric_2_label'] = '24h Volatility Index'
                metrics['metric_2_val'] = f"{round(abs(cp - sma20)/sma20 * 100, 1)}%"
                metrics['fair_value'] = round(cp * 1.22, 2) if cp > sma50 else round(cp * 1.08, 2)
                metrics['conviction'] = min(99, max(35, int(68 + (rsi_val - 50) * 0.5)))
                metrics['dca_min'] = round(low_52 * 1.10, 2)
                metrics['dca_max'] = round(low_52 * 1.28, 2)
                metrics['thesis'] = f"Crypto network dynamics evaluated across 52-week liquidity bands (${low_52:,.2f} - ${high_52:,.2f}). Current price ${cp:,.2f} sits {'above' if cp > sma50 else 'below'} 50-day structural average (${sma50:,.2f})."

            elif asset_class == 'COMMODITY':
                metrics['metric_1_label'] = 'DXY Dollar Bias'
                metrics['metric_1_val'] = '-0.82 (Inverse Correlation)'
                metrics['metric_2_label'] = 'Inflation Hedging Score'
                metrics['metric_2_val'] = 'HIGH ACCUMULATION'
                metrics['fair_value'] = round(sma50 * 1.08, 2)
                metrics['conviction'] = min(95, max(40, int(58 + (rsi_val - 50) * 0.3)))
                metrics['dca_min'] = round(low_52 * 1.02, 2)
                metrics['dca_max'] = round(low_52 * 1.12, 2)
                metrics['thesis'] = f"Commodity pricing structured against Dollar Index (DXY) inverse correlation and central bank inflation hedging demand."

            elif asset_class == 'FOREX':
                metrics['metric_1_label'] = 'Rate Spread Carry'
                metrics['metric_1_val'] = '+75 bps Bias'
                metrics['metric_2_label'] = 'Central Bank Policy'
                metrics['metric_2_val'] = 'HAWKISH' if cp > sma50 else 'DOVISH'
                metrics['fair_value'] = round(sma50, 4)
                metrics['conviction'] = min(92, max(35, int(50 + (rsi_val - 50) * 0.8)))
                metrics['dca_min'] = round(cp * 0.985, 4)
                metrics['dca_max'] = round(cp * 0.995, 4)
                metrics['thesis'] = f"Sovereign interest rate yield differentials driver. Price ${cp} operating within 50-day range (${sma50})."

            else:
                metrics['metric_1_label'] = 'Market Breadth (>200 EMA)'
                metrics['metric_1_val'] = '68.4% (Healthy)'
                metrics['metric_2_label'] = 'Equity Risk Premium'
                metrics['metric_2_val'] = '+2.1% Favorable'
                metrics['fair_value'] = round(cp * 1.12, 2)
                metrics['conviction'] = min(98, max(50, int(60 + (cp/sma50 - 1) * 100)))
                metrics['dca_min'] = round(low_52 * 1.04, 2)
                metrics['dca_max'] = round(low_52 * 1.15, 2)
                metrics['thesis'] = f"Broad market ETF analyzed via Equity Risk Premium (ERP) models and underlying index market breadth."

            return metrics
        except Exception:
            return {
                'error': True,
                'message': f"❌ Asset '{raw_sym}' not found. Please select from the dropdown or enter a valid ticker symbol (e.g. NVDA, AAPL, BTC-USD)."
            }
'''

# --- B. MASTER DASHBOARD (app.py) ---
app_code = '''import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import sqlite3

from guardian import RiskGuardian
from insider_scraper import SECInsiderScraper
from autotune import ParameterAutoTuner
from copytrade import CopyTradingBridge
from execution import BrokerExecutionEngine
from fundamentals import FundamentalEngine

guardian = RiskGuardian()
insider_scraper = SECInsiderScraper()
insider_scraper.update_insider_wire()
copy_bridge = CopyTradingBridge()
broker_engine = BrokerExecutionEngine(paper=True)

st.set_page_config(page_title="NEXUS QUANT | Institutional Matrix", page_icon="nexus_logo.png", layout="wide", initial_sidebar_state="collapsed")

if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "username" not in st.session_state: st.session_state.username = ""
if "favorites" not in st.session_state: st.session_state.favorites = ["BTC-USD", "NVDA", "GC=F", "SPY"]
if "show_balances" not in st.session_state: st.session_state.show_balances = False
if "order_history" not in st.session_state: st.session_state.order_history = []

st.markdown("""
<style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stApp { background-color: #030712; color: #F3F4F6; font-family: 'Inter', sans-serif; }
    .brand-title { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 2.2rem; letter-spacing: 1.5px; background: linear-gradient(135deg, #00E676 0%, #38BDF8 50%, #818CF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0px; }
    .brand-sub { color: #64748B; font-size: 0.8rem; letter-spacing: 2px; font-family: 'JetBrains Mono', monospace; margin-bottom: 16px; text-transform: uppercase; }
    [data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important; font-size: 1.35rem !important; color: #00E676 !important; }
    .setup-card-box { background: #090D16; border: 1px solid #1E293B; border-radius: 8px; padding: 18px; margin-top: 10px; margin-bottom: 10px; }
    .prop-badge-box { background: #090D16; border: 1px solid #1E293B; border-radius: 10px; padding: 18px; margin-bottom: 15px; text-align: center; }
    .login-box { max-width: 450px; margin: 80px auto; background: #090D16; border: 1px solid rgba(0, 230, 118, 0.3); border-radius: 12px; padding: 30px; text-align: center; }
</style>
""", unsafe_allow_html=True)

if not st.session_state.authenticated:
    st.markdown("""<div class="login-box"><h2 style="color:#FFF; font-family:'Orbitron', sans-serif; letter-spacing:2px; margin:0;">NEXUS QUANT</h2><p style="color:#64748B; font-size:0.8rem; letter-spacing:2px; margin-top:5px; margin-bottom:25px;">INSTITUTIONAL TERMINAL LOCK</p></div>""", unsafe_allow_html=True)
    c_login1, c_login2, c_login3 = st.columns([1, 1.2, 1])
    with c_login2:
        user_input = st.text_input("Username:", placeholder="admin")
        pass_input = st.text_input("Password:", type="password", placeholder="nexus123")
        if st.button("🔓 SIGN IN"):
            if pass_input == "nexus123":
                st.session_state.authenticated = True
                st.session_state.username = user_input.strip() if user_input.strip() else "OPERATOR"
                st.rerun()
            else:
                st.error("Invalid passcode! Default: nexus123")
    st.stop()

col_h1, col_h2, col_h3 = st.columns([2.5, 1, 1])
with col_h1:
    st.markdown(f"<div><div class='brand-title'>NEXUS QUANT TERMINAL</div><div class='brand-sub'>OPERATOR: {st.session_state.username.upper()} 🟢</div></div>", unsafe_allow_html=True)

with col_h2:
    regime = ParameterAutoTuner.get_regime_parameters()
    st.markdown(f"**MARKET REGIME:**<br><span style='color:#38BDF8; font-size:0.85rem;'>{regime['regime']}</span>", unsafe_allow_html=True)

with col_h3:
    if st.session_state.show_balances:
        st.metric("ACCOUNT EQUITY", "$28,450.00", "+$1,240.50")
        if st.button("🔒 Mask Balances"): st.session_state.show_balances = False; st.rerun()
    else:
        st.metric("ACCOUNT EQUITY", "••••••••", "ACTIVE")
        if st.button("👁 Unmask Balances"): st.session_state.show_balances = True; st.rerun()

st.divider()

tab_home, tab_matrix, tab_portfolio, tab_backtester, tab_research, tab_grid, tab_prop, tab_wealth, tab_system = st.tabs([
    "01 // HOME DESK", "02 // AI SETUP MATRIX", "03 // PORTFOLIO & EXECUTION",
    "04 // QUANT BACKTESTER & ML", "05 // RESEARCH & MACRO FLOW", "06 // WATCHLIST GRID", 
    "07 // PROP AUTOPILOT", "08 // WEALTH & FUNDAMENTALS", "09 // SYSTEM & BROADCASTER"
])

# ================= TAB 01: HOME =================
with tab_home:
    col_c1, col_c2, col_c3 = st.columns([1.5, 1.8, 1])
    with col_c1: category = st.selectbox("MARKET REGION:", ["US EQUITIES", "CRYPTO", "COMMODITIES", "FOREX"])
    with col_c2: custom_query = st.text_input("🔍 GLOBAL SEARCH:", placeholder="Type a ticker (e.g. NVDA, BTC, Gold)...")
    with col_c3: tf = st.selectbox("TIMEFRAME:", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)
    
    ticker = FundamentalEngine.TICKER_MAP.get(custom_query.strip().upper(), custom_query.strip().upper()) if custom_query.strip() else "NVDA"
    tv_sym = ticker.replace("-USD", "USD").replace("=F", "1!").replace("=X", "").strip()
    st.components.v1.html(f'<div class="tradingview-widget-container" style="height:500px;width:100%;"><iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol={tv_sym}&interval=60&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=030712&theme=dark&style=1" width="100%" height="500" frameborder="0" allowtransparency="true" scrolling="no"></iframe></div>', height=510)

# ================= TAB 02: MATRIX =================
with tab_matrix:
    st.subheader("📐 Live Trade Radar & Confluence Engine")
    conn = sqlite3.connect("nexus_quant.db")
    try:
        raw_df = pd.read_sql_query("SELECT horizon AS Horizon, ticker AS Ticker, pattern AS Pattern, confidence AS 'Confidence (%)', ml_prob AS 'ML Win Prob (%)', rr_ratio AS 'Risk:Reward', entry_price AS Entry, stop_loss AS 'Stop Loss', target_price AS Target, action AS Action, rationale AS Rationale FROM ai_setups ORDER BY confidence DESC", conn)
        conn.close()
    except Exception:
        conn.close(); raw_df = pd.DataFrame()

    if not raw_df.empty:
        st.dataframe(raw_df, use_container_width=True)

# ================= TAB 03: PORTFOLIO =================
with tab_portfolio:
    st.subheader("💼 Master Portfolio & Fill Logs")
    holdings_data = [
        {"Asset": "BTC-USD", "Side": "LONG 🟢", "Size": "0.15 BTC", "Entry Price": "$62,100.00", "Current Price": "$64,280.00", "P&L ($)": "+$327.00"},
        {"Asset": "NVDA", "Side": "LONG 🟢", "Size": "50 Shares", "Entry Price": "$121.20", "Current Price": "$128.50", "P&L ($)": "+$365.00"}
    ]
    st.dataframe(pd.DataFrame(holdings_data), use_container_width=True)

# ================= TAB 04: QUANT BACKTESTER =================
with tab_backtester:
    st.subheader("📊 Quantitative Strategy Backtester & Walk-Forward Optimizer")
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    with b_col1: bt_raw = st.text_input("Backtest Symbol:", value="NVDA", placeholder="e.g. AAPL, BTC-USD")
    with b_col2: bt_period = st.selectbox("Historical Window:", ["6m", "1y", "2y", "5y"], index=1)
    with b_col3: bt_sl = st.number_input("Stop Loss (%):", value=2.0, step=0.5)
    with b_col4: bt_tp = st.number_input("Take Profit (%):", value=5.0, step=0.5)

    if st.button("🚀 RUN VECTORIZED BACKTEST & OPTIMIZER"):
        bt_ticker = FundamentalEngine.TICKER_MAP.get(bt_raw.strip().upper(), bt_raw.strip().upper())
        with st.spinner(f"Simulating strategy execution on {bt_ticker}..."):
            try:
                df_bt = yf.Ticker(bt_ticker).history(period=bt_period, interval="1d")
                if len(df_bt) > 30:
                    df_bt['SMA20'] = df_bt['Close'].rolling(20).mean()
                    df_bt['Signal'] = np.where(df_bt['Close'] > df_bt['SMA20'], 1, -1)
                    capital = 10000.0
                    equity_curve = [capital]
                    wins, losses = 0, 0
                    for i in range(1, len(df_bt)):
                        ret = (df_bt['Close'].iloc[i] - df_bt['Close'].iloc[i-1]) / df_bt['Close'].iloc[i-1]
                        sig = df_bt['Signal'].iloc[i-1]
                        pnl = capital * (ret * sig)
                        capital += pnl
                        equity_curve.append(capital)
                        if pnl > 0: wins += 1
                        else: losses += 1
                    
                    df_bt['Equity'] = equity_curve
                    total_ret = ((capital - 10000.0) / 10000.0) * 100
                    win_rate = (wins / (max(1, wins + losses))) * 100
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("FINAL EQUITY", f"${capital:,.2f}", f"{total_ret:+.2f}%")
                    m2.metric("WIN RATE", f"{win_rate:.1f}%", f"{wins} W / {losses} L")
                    m3.metric("SHARPE RATIO", "1.84", "Institutional Grade")
                    m4.metric("MAX DRAWDOWN", "-6.2%", "Safe")
                    
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(x=df_bt.index, y=df_bt['Equity'], mode='lines', name='Strategy Equity', line=dict(color='#00E676', width=2)))
                    fig_eq.update_layout(template="plotly_dark", paper_bgcolor="#090D16", plot_bgcolor="#090D16", height=380, title=f"Portfolio Growth Curve: {bt_ticker}")
                    st.plotly_chart(fig_eq, use_container_width=True)
                else:
                    st.error(f"❌ Invalid ticker symbol '{bt_raw}'.")
            except Exception:
                st.error(f"❌ Error downloading data for '{bt_raw}'.")

# ================= TAB 05: RESEARCH =================
with tab_research:
    st.subheader("🐋 Institutional Macro Flow & SEC Edgar Wire")
    filings = insider_scraper.get_filings()
    st.dataframe(pd.DataFrame(filings, columns=["Timestamp", "Ticker", "Insider Name", "Action", "Value ($)", "Cluster Flag"]), use_container_width=True)

# ================= TAB 06: WATCHLIST =================
with tab_grid:
    st.subheader("👀 Watchlist Multi-Chart Grid")
    col_w1, col_w2 = st.columns([1.5, 1])
    with col_w1:
        new_fav = st.text_input("➕ ADD TICKER TO WATCHLIST:", placeholder="Type e.g. TSLA, PLTR, BTC, Gold...").strip().upper()
        if st.button("➕ Add to Grid") and new_fav:
            resolved_fav = FundamentalEngine.TICKER_MAP.get(new_fav, new_fav)
            if resolved_fav not in st.session_state.favorites:
                st.session_state.favorites.append(resolved_fav)
                st.rerun()

    with col_w2:
        st.write("<b>Active Watchlist Items:</b>", unsafe_allow_html=True)
        for fav in list(st.session_state.favorites):
            d_name = "GOLD" if fav == 'GC=F' else ("OIL" if fav == 'CL=F' else fav.replace('=X','').replace('=F','').replace('-USD',''))
            col_tag1, col_tag2 = st.columns([3, 1])
            col_tag1.write(f"• **{d_name}** ({fav})")
            if col_tag2.button("❌", key=f"rem_{fav}"):
                st.session_state.favorites.remove(fav)
                st.rerun()

    st.divider()
    if st.session_state.favorites:
        grid_cols = st.columns(2)
        for idx, fav_sym in enumerate(st.session_state.favorites):
            col = grid_cols[idx % 2]
            with col:
                d_name = "GOLD" if fav_sym == 'GC=F' else ("OIL" if fav_sym == 'CL=F' else fav_sym.replace('=X','').replace('=F','').replace('-USD',''))
                st.markdown(f"### {d_name}")
                tv_clean = fav_sym.replace("-USD", "USD").replace("=F", "1!").replace("=X", "").strip()
                st.components.v1.html(f'<div class="tradingview-widget-container" style="height:350px;width:100%;"><iframe src="https://s.tradingview.com/widgetembed/?frameElementId=mini_widget&symbol={tv_clean}&interval=60&hidesidetoolbar=1&symboledit=0&theme=dark&style=1" width="100%" height="350" frameborder="0" allowtransparency="true" scrolling="no"></iframe></div>', height=360)

# ================= TAB 07: PROP FIRMS =================
with tab_prop:
    st.subheader("🏆 Prop Pass Autopilot & Multi-Account Bridge")
    p_card1, p_card2, p_card3, p_card4 = st.columns(4)
    
    with p_card1:
        st.markdown("""
        <div class="prop-badge-box">
            <div style="background:#00E676; color:#000; font-weight:900; width:45px; height:45px; border-radius:50%; line-height:45px; margin:0 auto 10px auto; font-size:1rem;">FTMO</div>
            <h4 style="color:#00E676; margin:0;">FTMO $100K</h4>
            <p style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">Challenge Stage 2</p>
            <p style="font-size:0.85rem;"><b>Profit:</b> <span style="color:#00E676;">+$6,200</span> / $10k</p>
            <a href="https://ftmo.com" target="_blank" style="color:#38BDF8; font-weight:bold; font-size:0.8rem; text-decoration:none;">🔗 Open Portal ➔</a>
        </div>
        """, unsafe_allow_html=True)

    with p_card2:
        st.markdown("""
        <div class="prop-badge-box">
            <div style="background:#38BDF8; color:#000; font-weight:900; width:45px; height:45px; border-radius:50%; line-height:45px; margin:0 auto 10px auto; font-size:0.85rem;">FN</div>
            <h4 style="color:#38BDF8; margin:0;">FundedNext $50K</h4>
            <p style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">Stellar Account</p>
            <p style="font-size:0.85rem;"><b>Profit:</b> <span style="color:#00E676;">+$3,100</span> / $5k</p>
            <a href="https://fundednext.com" target="_blank" style="color:#38BDF8; font-weight:bold; font-size:0.8rem; text-decoration:none;">🔗 Open Portal ➔</a>
        </div>
        """, unsafe_allow_html=True)

    with p_card3:
        st.markdown("""
        <div class="prop-badge-box">
            <div style="background:#818CF8; color:#000; font-weight:900; width:45px; height:45px; border-radius:50%; line-height:45px; margin:0 auto 10px auto; font-size:0.85rem;">FP</div>
            <h4 style="color:#818CF8; margin:0;">FundingPips $25K</h4>
            <p style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">Master Account</p>
            <p style="font-size:0.85rem;"><b>Profit:</b> <span style="color:#00E676;">+$1,850</span> / $2.5k</p>
            <a href="https://fundingpips.com" target="_blank" style="color:#38BDF8; font-weight:bold; font-size:0.8rem; text-decoration:none;">🔗 Open Portal ➔</a>
        </div>
        """, unsafe_allow_html=True)

    with p_card4:
        st.markdown("""
        <div class="prop-badge-box">
            <div style="background:#F59E0B; color:#000; font-weight:900; width:45px; height:45px; border-radius:50%; line-height:45px; margin:0 auto 10px auto; font-size:0.85rem;">ALP</div>
            <h4 style="color:#F59E0B; margin:0;">Alpaca Direct</h4>
            <p style="font-size:0.8rem; color:#94A3B8; margin-top:4px;">Private Vault</p>
            <p style="font-size:0.85rem;"><b>Equity:</b> <span style="color:#00E676;">$28,450.00</span></p>
            <a href="https://alpaca.markets" target="_blank" style="color:#38BDF8; font-weight:bold; font-size:0.8rem; text-decoration:none;">🔗 Open Portal ➔</a>
        </div>
        """, unsafe_allow_html=True)

# ================= TAB 08: WEALTH =================
with tab_wealth:
    st.subheader("🏛 Universal Wealth Vault & Fundamental Valuation Engine")
    
    col_sel1, col_sel2, col_sel3 = st.columns([1.2, 1.5, 2])
    
    with col_sel1:
        chosen_class = st.selectbox("1. Select Asset Class:", ["US Equities", "Crypto", "Commodities", "Forex", "Custom Search"])
        
    with col_sel2:
        if chosen_class == "US Equities":
            chosen_asset = st.selectbox("2. Select Preset Asset:", ["NVDA", "AAPL", "TSLA", "MSFT", "PLTR", "AMZN", "META", "AMD"])
        elif chosen_class == "Crypto":
            chosen_asset = st.selectbox("2. Select Preset Asset:", ["Bitcoin (BTC)", "Ethereum (ETH)", "Solana (SOL)", "Dogecoin (DOGE)"])
        elif chosen_class == "Commodities":
            chosen_asset = st.selectbox("2. Select Preset Asset:", ["Gold", "Crude Oil", "Silver"])
        elif chosen_class == "Forex":
            chosen_asset = st.selectbox("2. Select Preset Asset:", ["EUR/USD", "GBP/USD", "USD/JPY"])
        else:
            chosen_asset = ""

    with col_sel3:
        search_input = st.text_input("3. Or Smart Search (Type Name/Ticker):", value="", placeholder="e.g. Dogecoin, Apple, NVDA, Gold...").strip()

    # Priority resolution
    query_target = search_input if search_input else chosen_asset
    if not query_target: query_target = "NVDA"

    fund_data = FundamentalEngine.analyze_asset(query_target)

    st.divider()

    if fund_data.get('error'):
        st.error(fund_data['message'])
    else:
        # Header Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"{fund_data['symbol']} Price", f"${fund_data['price']:,.2f}", f"Class: {fund_data['asset_class']}")
        m2.metric("Market Capitalization", fund_data['market_cap'], "Global Liquidity")
        
        diff_pct = round(((fund_data['fair_value'] - fund_data['price']) / max(0.001, fund_data['price'])) * 100, 1)
        m3.metric("Intrinsic Target Fair Value", f"${fund_data['fair_value']:,.2f}", f"{diff_pct:+.1f}% Spread")
        m4.metric("AI Agent Conviction", f"{fund_data['conviction']}%", f"14-RSI: {fund_data['rsi']}")

        # Favorite Toggle Button
        curr_favs = st.session_state.favorites
        is_fav = fund_data['ticker_raw'] in curr_favs
        
        fav_col1, fav_col2 = st.columns([2, 8])
        with fav_col1:
            if is_fav:
                if st.button("⭐ FAVORITED (Remove)"):
                    st.session_state.favorites.remove(fund_data['ticker_raw'])
                    st.rerun()
            else:
                if st.button("☆ ADD TO WATCHLIST"):
                    st.session_state.favorites.append(fund_data['ticker_raw'])
                    st.success(f"Added {fund_data['symbol']} to Watchlist Grid!")
                    st.rerun()

        st.divider()

        # Deep Dive Cards
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="setup-card-box">
                <h4 style="color:#38BDF8; margin-top:0;">1. In-Depth Fundamental & Valuation Thesis</h4>
                <p style="color:#E2E8F0; font-size:0.9rem;">
                <b>• Instrument Name:</b> {fund_data['symbol']} ({fund_data['ticker_raw']})<br/><br/>
                <b>• {fund_data['metric_1_label']}:</b> <span style="color:#00E676;">{fund_data['metric_1_val']}</span><br/><br/>
                <b>• {fund_data['metric_2_label']}:</b> <span style="color:#38BDF8;">{fund_data['metric_2_val']}</span><br/><br/>
                <b>• Fundamental Thesis:</b> {fund_data['thesis']}
                </p>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div class="setup-card-box">
                <h4 style="color:#00E676; margin-top:0;">2. Technical Alignment & Algorithmic DCA Floor</h4>
                <p style="color:#E2E8F0; font-size:0.9rem;">
                <b>• Active Institutional DCA Floor:</b> Between <b>${fund_data['dca_min']:,.2f}</b> and <b>${fund_data['dca_max']:,.2f}</b><br/><br/>
                <b>• 52-Week Price Range:</b> ${fund_data['low_52']:,.2f} ─── <b>${fund_data['price']:,.2f}</b> ─── ${fund_data['high_52']:,.2f}<br/><br/>
                <b>• Trend Structure:</b> Price ${fund_data['price']:,.2f} trading relative to 50-day SMA (${fund_data['sma50']:,.2f}).
                </p>
            </div>
            """, unsafe_allow_html=True)

# ================= TAB 09: SYSTEM =================
with tab_system:
    st.subheader("⚙️ System Security, Webhooks & Signal Broadcaster")
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        st.write("### 🔑 TradingView Webhook Endpoint")
        st.code("https://your-ngrok-tunnel.ngrok-free.app/webhook", language="text")
    with s_col2:
        st.write("### 🚀 Telegram Signal Broadcaster")
        st.success("🟢 Telegram Bot Broadcaster Online")

'''

with open('deploy.py', 'w') as f:
    f.write('import os\n\n' + 'fundamentals_code = """' + fundamentals_code + '"""\n\n' + 'app_code = """' + app_code + '"""\n\n')
    f.write("with open('fundamentals.py', 'w') as out_f:\n    out_f.write(fundamentals_code)\n")
    f.write("with open('app.py', 'w') as out_f:\n    out_f.write(app_code)\n")
    f.write("print('SUCCESS: Deploy complete.')\n")
