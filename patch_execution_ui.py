with open("app.py", "r") as f:
    code = f.read()

execution_import = "from execution import BrokerExecutionEngine\nbroker_engine = BrokerExecutionEngine(paper=True)\n"

if "from execution import BrokerExecutionEngine" not in code:
    code = execution_import + code
    
    # Replace simple paper log button with full broker execution engine call
    old_btn = 'if st.button(f"🚀 EXECUTE {selected_setup.get(\'Action\')} ON PAPER ACCOUNT"):'
    new_btn = '''if st.button(f"🚀 EXECUTE {selected_setup.get('Action')} (LIVE OCO BRACKET)"):
                    success, msg = broker_engine.execute_bracket_order(
                        selected_setup.get('Ticker'),
                        selected_setup.get('Action'),
                        10,
                        float(selected_setup.get('Entry', 100)),
                        float(selected_setup.get('Stop Loss', 95)),
                        float(selected_setup.get('Target', 110))
                    )
                    if success:
                        st.success(f"Broker Response: {msg}")
                        st.session_state.order_history.append({"Time": datetime.datetime.now().strftime("%H:%M:%S"), "Ticker": selected_setup.get('Ticker'), "Side": selected_setup.get('Action'), "Price": selected_setup.get('Entry'), "Status": "OCO BRACKET ACTIVE"})
                    else:
                        st.error(f"Execution Failed: {msg}")'''
    
    code = code.replace(old_btn, new_btn)
    with open("app.py", "w") as f:
        f.write(code)
    print("SUCCESS: app.py successfully linked to execution.py!")
