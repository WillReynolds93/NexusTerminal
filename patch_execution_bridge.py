with open("execution.py", "r") as f:
    code = f.read()

copy_import = "from copytrade import CopyTradingBridge\ncopy_bridge = CopyTradingBridge()\n"

if "from copytrade import CopyTradingBridge" not in code:
    code = copy_import + code
    old_log_call = "self._log_trade_to_db(timestamp, ticker, action, qty, entry_price, stop_loss, target_price, \"FILLED\")"
    new_log_call = """self._log_trade_to_db(timestamp, ticker, action, qty, entry_price, stop_loss, target_price, "FILLED")
            copy_bridge.dispatch_multi_account_orders(ticker, action, entry_price, stop_loss, target_price)"""
            
    code = code.replace(old_log_call, new_log_call)
    with open("execution.py", "w") as f:
        f.write(code)
    print("SUCCESS: execution.py now triggers copytrade.py on every execution!")
