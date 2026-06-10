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
            "method": "llm" if self.sentiment_engine.use_llm else "heuristic",
            "symbol": symbol,
            "sentiment_score": score,
            "market_bias": bias,
            "reasoning": f"Sentiment score {score:.2f} via "
                         f"{'Groq LLM' if self.sentiment_engine.use_llm else 'heuristic scorer'}, "
                         f"yielding a {bias} bias."
        }
