cat << 'INNER_EOF' > execution.py
import os
import requests
from dotenv import load_dotenv
from db import CloudDatabaseManager

load_dotenv()

class BrokerExecutionEngine:
    def __init__(self, paper=True):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }

    def check_account_health(self):
        """Checks Alpaca connection or defaults to internal Cloud Simulator."""
        if self.api_key and "YOUR_ALPACA" not in self.api_key:
            try:
                res = requests.get(f"{self.base_url}/v2/account", headers=self.headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "mode": "ALPACA PAPER 🟢",
                        "equity": float(data.get("equity", 100000.0)),
                        "buying_power": float(data.get("buying_power", 200000.0))
                    }
            except Exception:
                pass
        
        # Fallback to Built-in Neon Virtual Simulator
        return {
            "mode": "NEON VIRTUAL SIMULATOR 🟢",
            "equity": 100000.00,
            "buying_power": 200000.00
        }

    def execute_bracket_order(self, symbol, qty, side, entry_price, take_profit, stop_loss, strategy_tag="SCALP"):
        """Executes via Alpaca if available, or logs directly to Neon Cloud DB."""
        health = self.check_account_health()
        
        if "ALPACA" in health["mode"]:
            url = f"{self.base_url}/v2/orders"
            payload = {
                "symbol": symbol.upper().replace("-USD", "").replace("=F", ""),
                "qty": qty,
                "side": side.lower(),
                "type": "market",
                "time_in_force": "gtc",
                "order_class": "bracket",
                "take_profit": {"limit_price": round(take_profit, 2)},
                "stop_loss": {"stop_price": round(stop_loss, 2)}
            }
            try:
                res = requests.post(url, json=payload, headers=self.headers, timeout=5)
                return res.json()
            except Exception as e:
                return {"error": str(e)}
        else:
            # Simulate fill locally and save order directly into Neon Postgres DB
            try:
                conn = CloudDatabaseManager.get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO order_history (ticker, strategy_tag, account_id, side, size, entry_price, stop_loss, target_price, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (symbol, strategy_tag, "NEON_SIMULATOR_01", side, str(qty), entry_price, stop_loss, take_profit, "EXECUTED (PAPER)"))
                conn.commit()
                cur.close()
                conn.close()
                return {"status": "SUCCESS", "message": f"Simulated {side} order for {symbol} saved to Neon Cloud!"}
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
INNER_EOF

print("✅ Built-in Cloud Simulator successfully enabled in execution.py!")
