import re

with open("app.py", "r") as f:
    code = f.read()

# Replace the old slider with the new wide scale and auto-refresh button
old_slider_section = """    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        min_conf = st.slider("Min Agent Confidence Score (%)", 50, 98, 80)
    with f_col2:
        sort_by = st.selectbox("Sort Setups By:", ["Confidence Score (High-to-Low)", "Risk:Reward Ratio", "Ticker A-Z"])
    with f_col3:
        sel_asset = st.selectbox("Asset Filter:", ["All Markets", "US Equities", "Crypto", "Commodities", "Forex"])"""

new_slider_section = """    f_col1, f_col2, f_col3, f_col4 = st.columns([1.5, 1.5, 1, 1])
    with f_col1:
        min_conf = st.slider("🧠 Filter by Agent Confluence Score", 10, 99, 60, help="Lower score = more setups. Higher score = strictly filtered institutional trades.")
    with f_col2:
        sort_by = st.selectbox("Sort Setups By:", ["Confidence Score (High-to-Low)", "Risk:Reward Ratio", "Ticker A-Z"])
    with f_col3:
        sel_asset = st.selectbox("Asset Filter:", ["All Markets", "US Equities", "Crypto", "Commodities"])
    with f_col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Poll Live Brain Radar"):
            st.rerun()"""

if "🧠 Filter by Agent Confluence" not in code:
    code = code.replace(old_slider_section, new_slider_section)
    with open("app.py", "w") as f:
        f.write(code)
    print("SUCCESS: Streamlit UI updated with Wide-Scale Slider and Live Radar!")
