import os
from loguru import logger

class SentimentEngine:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        
        self.use_llm = bool(self.groq_key)
        if self.use_llm:
            logger.info(f"AI Sentiment Engine initialized using Groq API ({self.groq_model}).")
        else:
            logger.warning("No GROQ_API_KEY found. Falling back to heuristic dictionary scorer.")

    def score_text(self, text: str) -> float:
        """
        Analyzes financial news sentiment.
        Returns a float between -1.0 (very bearish) and +1.0 (very bullish).
        """
        if not text.strip():
            return 0.0

        if self.use_llm:
            return self._score_with_groq(text)
        
        return self._score_heuristic(text)

    def _score_with_groq(self, text: str) -> float:
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            prompt = (
                "You are an expert quantitative sentiment analyst. Analyze the following financial text "
                "and return ONLY a single floating-point number between -1.0 (most bearish) and +1.0 (most bullish) "
                "representing the sentiment. Do not write explanations, markdown, or code. Text:\n"
                f"{text}"
            )
            response = client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            score = float(response.choices[0].message.content.strip())
            return max(-1.0, min(1.0, score))
        except Exception as e:
            logger.error(f"Groq API Error: {e}. Falling back to heuristic.")
            return self._score_heuristic(text)

    def _score_heuristic(self, text: str) -> float:
        bullish_words = {"surge", "profit", "bullish", "growth", "high", "gain", "raise", "outperform", "buy", "upbeat", "earnings", "dividend"}
        bearish_words = {"slump", "loss", "bearish", "decline", "low", "drop", "cut", "underperform", "sell", "warn", "debt", "risk", "shortfall"}
        
        words = text.lower().split()
        bull_count = sum(1 for w in words if any(bw in w for bw in bullish_words))
        bear_count = sum(1 for w in words if any(bw in w for bw in bearish_words))
        
        total = bull_count + bear_count
        if total == 0:
            return 0.0
        return (bull_count - bear_count) / total
