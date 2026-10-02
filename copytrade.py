import sqlite3
import datetime

class CopyTradingBridge:
    """Intermits master execution signals and replicates them across multiple prop/broker accounts."""
    
    def __init__(self):
        self.db_path = "nexus_quant.db"
        self._init_account_vault()

    def _init_account_vault(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prop_accounts (
            account_id TEXT PRIMARY KEY,
            firm_name TEXT,
            account_type TEXT,
            balance REAL,
            max_daily_loss REAL,
            risk_pct REAL,
            status TEXT
        )
        """)
        
        # Seed default slave prop accounts if empty
        cursor.execute("SELECT COUNT(*) FROM prop_accounts")
        if cursor.fetchone()[0] == 0:
            defaults = [
                ("FTMO-100K-01", "FTMO", "$100,000 Challenge", 100000.0, 5000.0, 0.50, "ACTIVE 🟢"),
                ("FN-50K-02", "FundedNext", "$50,000 Stellar", 50000.0, 2500.0, 0.50, "ACTIVE 🟢"),
                ("FP-25K-03", "FundingPips", "$25,000 Master", 25000.0, 1250.0, 0.50, "ACTIVE 🟢"),
                ("ALP-PAPER-01", "Alpaca Direct", "Private Vault", 28450.0, 1422.5, 0.50, "ACTIVE 🟢")
            ]
            cursor.executemany("INSERT INTO prop_accounts VALUES (?, ?, ?, ?, ?, ?, ?)", defaults)
            
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS copytrade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            account_id TEXT,
            firm_name TEXT,
            ticker TEXT,
            action TEXT,
            calc_qty REAL,
            risk_dollars REAL,
            status TEXT
        )
        """)
        conn.commit()
        conn.close()

    def calculate_scaled_quantity(self, balance, risk_pct, entry_price, stop_loss):
        """Calculates exact lot/share size based on individual account balance and stop loss distance."""
        stop_dist = abs(entry_price - stop_loss)
        if stop_dist <= 0:
            stop_dist = entry_price * 0.02 # 2% default fallback
            
        max_risk_dollars = balance * (risk_pct / 100.0)
        calc_qty = max_risk_dollars / stop_dist
        
        # Round appropriately for crypto vs equities
        return round(calc_qty, 4) if entry_price > 1000 else round(calc_qty, 2), max_risk_dollars

    def dispatch_multi_account_orders(self, ticker, action, entry_price, stop_loss, target_price):
        """Replicates master trade signal across all active slave accounts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT account_id, firm_name, balance, risk_pct FROM prop_accounts WHERE status LIKE 'ACTIVE%'")
        accounts = cursor.fetchall()
        
        results = []
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for acc_id, firm, balance, risk_pct in accounts:
            qty, risk_dollars = self.calculate_scaled_quantity(balance, risk_pct, entry_price, stop_loss)
            
            # Dispatch simulation / bridge payload
            log_status = "REPLICATED (OCO BRACKET ACTIVE)"
            cursor.execute("""
            INSERT INTO copytrade_logs (timestamp, account_id, firm_name, ticker, action, calc_qty, risk_dollars, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, acc_id, firm, ticker, action, qty, risk_dollars, log_status))
            
            results.append({
                "Account": acc_id,
                "Firm": firm,
                "Size": f"{qty} units",
                "Max Risk": f"${risk_dollars:,.2f}",
                "Status": log_status
            })
            
        conn.commit()
        conn.close()
        return results

    def get_registered_accounts(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT account_id, firm_name, account_type, balance, risk_pct, status FROM prop_accounts")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_execution_logs(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, account_id, firm_name, ticker, action, calc_qty, risk_dollars, status FROM copytrade_logs ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        return rows

if __name__ == "__main__":
    bridge = CopyTradingBridge()
    res = bridge.dispatch_multi_account_orders("NVDA", "BUY / LONG", 128.50, 126.00, 134.75)
    print("Multi-Account Replicate Test:")
    for r in res:
        print(f"  └─ {r['Account']} ({r['Firm']}): {r['Size']} | Risk: {r['Max Risk']} | {r['Status']}")
