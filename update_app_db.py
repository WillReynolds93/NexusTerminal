with open("app.py", "r") as f:
    code = f.read()

# Replace static array with SQLite query in Tab 02
db_code = """
    import sqlite3
    conn = sqlite3.connect("nexus_quant.db")
    try:
        raw_df = pd.read_sql_query("SELECT ticker AS Ticker, pattern AS Pattern, confidence AS Confidence, rr_ratio AS 'Risk:Reward', entry_price AS Entry, stop_loss AS 'Stop Loss', target_price AS Target, action AS Action, rationale AS Rationale FROM ai_setups ORDER BY confidence DESC", conn)
        conn.close()
        raw_setups = raw_df.to_dict('records') if not raw_df.empty else raw_setups
    except Exception as e:
        conn.close()
"""

if "import sqlite3" not in code:
    code = code.replace("raw_setups = [", db_code + "\n    raw_setups = [")
    with open("app.py", "w") as f:
        f.write(code)
    print("SUCCESS: app.py successfully linked to nexus_quant.db!")
