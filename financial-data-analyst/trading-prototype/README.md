Trading prototype (rule-based)

This folder contains a minimal rule-based trading prototype using yfinance for data and backtrader for backtesting.

Quickstart:
1. Create a virtualenv and install deps:
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Run a backtest (example):
   python backtest.py --ticker AAPL --start 2020-01-01 --end 2024-01-01

3. Get a quick paper signal for the latest data:
   python paper_trade.py --ticker AAPL --short 10 --long 30

Files:
- strategy.py: SMA crossover strategy for backtrader
- backtest.py: fetches data with yfinance and runs backtrader
- paper_trade.py: quick signal generator using latest bars

Notes:
- This is a prototype for experimentation (paper trading). Do not use for live trading without further testing and safeguards.
