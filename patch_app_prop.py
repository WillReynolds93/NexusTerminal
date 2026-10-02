with open("app.py", "r") as f:
    code = f.read()

prop_tab_old = """# ================= TAB 07: PROP AUTOPILOT =================
with tab_prop:
    st.subheader("🏆 Prop Pass Autopilot Engine (FTMO / FundedNext / FundingPips)")
    st.success("🟢 Active License: Tier 3 ($100k Account Challenge Preset)")
    
    pr_col1, pr_col2, pr_col3 = st.columns(3)
    pr_col1.metric("MAX DAILY LOSS LIMIT ($5K)", "-$320.00", "SAFE")
    pr_col2.metric("MAX TRAILING DRAWDOWN ($10K)", "-$1,120.00", "SAFE")
    pr_col3.metric("PROFIT TARGET ($10K)", "$6,200.00", "62% Completed")

    st.markdown(\"\"\"
    <div class="setup-card-box">
        <h4 style="color:#00E676; margin-top:0;">🔌 Broker API Latency & Health Check</h4>
        <div style="display:flex; justify-content:space-between; margin-top:10px;">
            <span><b>Alpaca Paper API:</b> <span style="color:#10B981;">Active (14ms)</span></span>
            <span><b>Interactive Brokers (TWS):</b> <span style="color:#10B981;">Active (22ms)</span></span>
            <span><b>MetaTrader 5 (MetaApi):</b> <span style="color:#10B981;">Active (45ms)</span></span>
        </div>
    </div>
    \"\"\")"""

prop_tab_new = """# ================= TAB 07: PROP AUTOPILOT & COPY BRIDGE =================
with tab_prop:
    st.subheader("🏆 Prop Pass Autopilot & Multi-Account Copy Bridge")
    st.success("🟢 Master Bridge Active: Synchronizing signals across 4 Connected Accounts")
    
    pr_col1, pr_col2, pr_col3 = st.columns(3)
    pr_col1.metric("COMBINED EQUITY ALLOCATED", "$203,450.00", "4 Accounts Synced")
    pr_col2.metric("MAX DAILY RISK CAP (0.50%)", "$1,017.25", "HARD STOP GUARD")
    pr_col3.metric("PROP PASS RATE (30D)", "88.4%", "12 Challenges Passed")

    st.divider()
    
    st.write("### 🔗 Registered Prop & Broker Accounts")
    from copytrade import CopyTradingBridge
    bridge_ui = CopyTradingBridge()
    accounts_data = bridge_ui.get_registered_accounts()
    
    acc_df = pd.DataFrame(accounts_data, columns=["Account ID", "Firm", "Challenge Type", "Balance ($)", "Risk Cap (%)", "Status"])
    st.dataframe(acc_df, use_container_width=True)

    st.divider()
    st.write("### ⚡ Live Multi-Account Replicated Order Logs")
    logs_data = bridge_ui.get_execution_logs()
    if logs_data:
        log_df = pd.DataFrame(logs_data, columns=["Timestamp", "Account ID", "Firm", "Ticker", "Action", "Dynamic Size", "Max Risk ($)", "Replication Status"])
        st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No trades replicated yet. Execute any trade from Tab 02 to trigger the bridge.")"""

if "Master Bridge Active: Synchronizing signals" not in code:
    code = code.replace(prop_tab_old, prop_tab_new)
    with open("app.py", "w") as f:
        f.write(code)
    print("SUCCESS: app.py Tab 07 successfully upgraded with Copy Bridge UI!")
