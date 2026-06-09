from sentiment import SentimentEngine

class MarketAnalystAgent:
    def __init__(self):
        self.sentiment_engine = SentimentEngine()

    def analyze(self, symbol: str, context_text: str) -> dict:
        """
        Analyzes news text context for a symbol and determines bias.
        """
        score = self.sentiment_engine.score_text(context_text)
        
        if score > 0.15:
            bias = "BULLISH"
        elif score < -0.15:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
            
        return {
            "agent": "Market Analyst Agent",
            "symbol": symbol,
            "sentiment_score": score,
            "market_bias": bias,
            "reasoning": f"Analyzed context. Sentiment score calculated as {score:.2f}, yielding a {bias} bias."
        }
