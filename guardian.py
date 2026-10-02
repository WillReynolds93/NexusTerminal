import sqlite3
import datetime

class RiskGuardian:
    def __init__(self, db_path="nexus_quant.db"):
        self.db_path = db_path

    def check_circuit_breaker(self, account_id="FTMO-100K-01", current_drawdown=320.0):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT max_daily_loss FROM prop_accounts WHERE account_id=?", (account_id,))
        row = cursor.fetchone()
        conn.close()
        
        max_daily = row[0] if row else 5000.0
        safety_cap = max_daily * 0.80
        
        if abs(current_drawdown) >= safety_cap:
            return False, f"CIRCUIT BREAKER TRIGGERED: Current loss (${abs(current_drawdown):,.2f}) exceeds safety cap (${safety_cap:,.2f})."
        return True, "RISK CLEAR: Drawdown within safe operational thresholds."

    def check_correlation_guard(self, ticker, action, active_positions):
        tech_cluster = {"NVDA", "AMD", "AAPL", "MSFT", "PLTR", "META", "GOOGL", "TSLA"}
        active_tech_longs = sum(1 for pos in active_positions if pos['Asset'] in tech_cluster and "LONG" in pos['Side'])
        
        if ticker in tech_cluster and "BUY" in action.upper() and active_tech_longs >= 2:
            return False, f"CORRELATION BLOCK: Already holding {active_tech_longs} Tech longs. Max sector exposure reached."
        return True, "CORRELATION CLEAR"
