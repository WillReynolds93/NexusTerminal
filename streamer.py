import asyncio
import json
import websockets
import sqlite3
import datetime

DB_PATH = "nexus_quant.db"

def update_live_price(ticker, price):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS live_ticks (
        ticker TEXT PRIMARY KEY,
        price REAL,
        timestamp TEXT
    )
    """)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    cursor.execute("INSERT OR REPLACE INTO live_ticks VALUES (?, ?, ?)", (ticker, price, timestamp))
    conn.commit()
    conn.close()

async def coinbase_streamer():
    """Streams live millisecond tick data from Coinbase public WebSocket feed."""
    url = "wss://ws-feed.exchange.coinbase.com"
    subscribe_msg = {
        "type": "subscribe",
        "product_ids": ["BTC-USD", "ETH-USD", "SOL-USD"],
        "channels": ["ticker"]
    }
    
    while True:
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(subscribe_msg))
                print("⚡ Zero-Latency WebSocket Streamer connected to market feed...")
                
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("type") == "ticker" and "price" in data:
                        ticker = data.get("product_id")
                        price = float(data.get("price"))
                        update_live_price(ticker, price)
        except Exception as e:
            print(f"WebSocket Reconnecting in 3s... ({e})")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(coinbase_streamer())
