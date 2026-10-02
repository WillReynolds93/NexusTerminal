from fastapi import FastAPI, HTTPException, Header, Request
import uvicorn
import os
from dotenv import load_dotenv
from execution import BrokerExecutionEngine

load_dotenv()
app = FastAPI(title="Nexus Quant Webhook Listener")
engine = BrokerExecutionEngine()
SECRET_TOKEN = "nexus_secure_bearer_token_2026"

@app.post("/api/v1/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    
    # Authenticate token
    token = data.get("secret")
    if token != SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized token")
    
    ticker = data.get("ticker", "NVDA")
    side = data.get("action", "BUY").upper()
    qty = float(data.get("qty", 10))
    entry = float(data.get("entry", 128.50))
    tp = float(data.get("tp", 139.70))
    sl = float(data.get("sl", 125.00))
    strategy_tag = data.get("strategy", "PINE_SCRIPT_WEBHOOK")

    # Execute trade via Execution Engine
    result = engine.execute_bracket_order(ticker, qty, side, entry, tp, sl, strategy_tag)
    print(f"⚡ WEBHOOK TRIGGERED: {side} {qty} {ticker} @ ${entry} -> {result}")
    
    return {"status": "SUCCESS", "execution": result}

if __name__ == "__main__":
    print("📡 Webhook listener starting on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
