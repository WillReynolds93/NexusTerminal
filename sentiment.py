import yfinance as yf
import re
import sqlite3

# Lexicon for financial sentiment scoring
BULLISH_WORDS = {'surge', 'growth', 'gain', 'profit', 'bullish', 'record', 'outperform', 'upgrade', 'beat', 'rally', 'positive', 'expansion', 'high'}
BEARISH_WORDS = {'drop', 'fall', 'loss', 'bearish', 'downgrade', 'miss', 'plunge', 'recession', 'slump', 'negative', 'decline', 'risk', 'crisis', 'cut'}

def analyze_ticker_sentiment(ticker):
    """Fetches wire headlines and returns an NLP sentiment score (-100 to +100)."""
    try:
        raw_news = yf.Ticker(ticker).news
        if not raw_news:
            return 0, "Neutral Market Noise"
            
        score = 0
        headlines_parsed = 0
        
        for item in raw_news[:5]:
            title = item.get('title', '').lower()
            tokens = set(re.findall(r'\w+', title))
            
            bull_count = len(tokens.intersection(BULLISH_WORDS))
            bear_count = len(tokens.intersection(BEARISH_WORDS))
            
            score += (bull_count - bear_count) * 20
            headlines_parsed += 1
            
        final_score = max(-100, min(100, score))
        summary = "Bullish Wire Sentiment" if final_score > 15 else ("Bearish Wire Sentiment" if final_score < -15 else "Neutral Market Noise")
        return final_score, summary
    except Exception as e:
        return 0, "Neutral Market Noise"

if __name__ == "__main__":
    score, summary = analyze_ticker_sentiment("NVDA")
    print(f"NVDA Sentiment Score: {score} ({summary})")
