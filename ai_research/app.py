import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.analyst import MarketAnalystAgent
from agents.portfolio import PortfolioManagerAgent
from agents.risk_analyst import RiskAnalystAgent
from agents.execution import ExecutionAgent

app = FastAPI(title="QuantForge AI Research Layer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate agents
analyst_agent = MarketAnalystAgent()
portfolio_agent = PortfolioManagerAgent()
risk_agent = RiskAnalystAgent()
execution_agent = ExecutionAgent()

class ResearchRequest(BaseModel):
    symbol: str
    news: str

@app.post("/analyze")
def run_research_pipeline(req: ResearchRequest):
    logger.info(f"[Research Pipeline] Starting research run for {req.symbol}...")
    
    # Step 1: Market Analyst Agent
    analyst_report = analyst_agent.analyze(req.symbol, req.news)
    logger.info(f"Market Analyst Result: {analyst_report['market_bias']}")

    # Step 2: Portfolio Manager Agent
    portfolio_proposal = portfolio_agent.rebalance(analyst_report)
    logger.info(f"Portfolio Manager Action: {portfolio_proposal['recommended_action']}")

    # Step 3: Risk Analyst Agent
    risk_report = risk_agent.validate_proposal(portfolio_proposal)
    logger.info(f"Risk Analyst Decision: Approved={risk_report['approved']}")

    # Step 4: Execution Agent
    execution_result = execution_agent.execute(risk_report)
    logger.info(f"Execution Agent Status: {execution_result['status']}")

    return {
        "status": "COMPLETED",
        "symbol": req.symbol,
        "pipeline_trace": [
            analyst_report,
            portfolio_proposal,
            risk_report,
            execution_result
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
