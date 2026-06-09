import os
from loguru import logger

class SentimentEngine:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        
        self.use_llm = bool(self.openai_key or self.gemini_key)
        if self.use_llm:
            logger.info("AI Sentiment Engine initialized using LLM APIs.")
        else:
            logger.warning("No AI keys found. Falling back to heuristic dictionary scorer.")

    def score_text(self, text: str) -> float:
        """
        Analyzes financial news sentiment.
        Returns a float between -1.0 (very bearish) and +1.0 (very bullish).
        """
        if not text.strip():
            return 0.0

        if self.use_llm:
            if self.gemini_key:
                return self._score_with_gemini(text)
            elif self.openai_key:
                return self._score_with_openai(text)
        
        return self._score_heuristic(text)

    def _score_with_gemini(self, text: str) -> float:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = (
                "You are an expert quantitative sentiment analyst. Analyze the following financial text "
                "and return ONLY a single floating-point number between -1.0 (most bearish) and +1.0 (most bullish) "
                "representing the sentiment. Do not write explanations, markdown, or code. Text:\n"
                f"{text}"
            )
            response = model.generate_content(prompt)
            score = float(response.text.strip())
            return max(-1.0, min(1.0, score))
        except Exception as e:
            logger.error(f"Gemini API Error: {e}. Falling back to heuristic.")
            return self._score_heuristic(text)

    def _score_with_openai(self, text: str) -> float:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            prompt = (
                "You are an expert quantitative sentiment analyst. Analyze the following financial text "
                "and return ONLY a single floating-point number between -1.0 (most bearish) and +1.0 (most bullish) "
                "representing the sentiment. Do not write explanations, markdown, or code. Text:\n"
                f"{text}"
            )
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            score = float(response.choices[0].message.content.strip())
            return max(-1.0, min(1.0, score))
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}. Falling back to heuristic.")
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
