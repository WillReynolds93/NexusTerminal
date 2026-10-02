import datetime

class ParameterAutoTuner:
    @staticmethod
    def get_regime_parameters(df=None):
        utc_hour = datetime.datetime.utcnow().hour
        if 7 <= utc_hour <= 11:
            return {"rsi_period": 9, "regime": "⚡ LONDON BREAKOUT (RSI-9)", "vol_status": "HIGH VOLATILITY"}
        elif 0 <= utc_hour <= 5:
            return {"rsi_period": 21, "regime": "🌙 ASIA CONSOLIDATION (RSI-21)", "vol_status": "LOW VOLATILITY"}
        else:
            return {"rsi_period": 14, "regime": "🎯 NY BALANCED REGIME (RSI-14)", "vol_status": "BALANCED"}
