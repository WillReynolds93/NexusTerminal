import sqlite3
import datetime

class SECInsiderScraper:
    def __init__(self, db_path="nexus_quant.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS insider_filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ticker TEXT,
            insider_name TEXT,
            action TEXT,
            value_usd REAL,
            cluster_flag INTEGER
        )
        """)
        conn.commit()
        conn.close()

    def update_insider_wire(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sample_filings = [
            (timestamp, "NVDA", "Huang, Jen-Hsun (CEO)", "BUY 🟢", 12500000.0, 1),
            (timestamp, "PLTR", "Karp, Alex (CEO)", "BUY 🟢", 4200000.0, 1),
            (timestamp, "CRWD", "Kurtz, George (CEO)", "BUY 🟢", 5400000.0, 1),
            (timestamp, "AMZN", "Bezos, Jeffrey (10%)", "SELL 🔴", 1200000000.0, 0),
            (timestamp, "COIN", "Armstrong, Brian (CEO)", "SELL 🔴", 12100000.0, 0)
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for f in sample_filings:
            cursor.execute("INSERT OR REPLACE INTO insider_filings (timestamp, ticker, insider_name, action, value_usd, cluster_flag) VALUES (?, ?, ?, ?, ?, ?)", f)
        conn.commit()
        conn.close()

    def get_filings(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, ticker, insider_name, action, value_usd, cluster_flag FROM insider_filings ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        return rows
