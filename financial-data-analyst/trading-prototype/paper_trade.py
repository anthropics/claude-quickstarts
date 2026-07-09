import argparse
import yfinance as yf
import pandas as pd


def get_signal(df: pd.DataFrame, short: int = 10, long: int = 30) -> str:
    df = df.copy()
    df['sma_short'] = df['Close'].rolling(short).mean()
    df['sma_long'] = df['Close'].rolling(long).mean()

    if len(df) < long + 1:
        return 'insufficient_data'

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # signal based on crossover between previous and last
    cross_prev = prev['sma_short'] - prev['sma_long']
    cross_last = last['sma_short'] - last['sma_long']

    if cross_prev <= 0 and cross_last > 0:
        return 'buy'
    if cross_prev >= 0 and cross_last < 0:
        return 'sell'
    return 'hold'


def main(ticker: str, short: int, long: int):
    df = yf.download(ticker, period='120d', progress=False)
    if df.empty:
        print('No data')
        return
    df.index = pd.to_datetime(df.index)
    signal = get_signal(df, short=short, long=long)
    print(f'Ticker: {ticker} | Signal: {signal} | Last Close: {df.Close.iloc[-1]:.2f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', required=True)
    parser.add_argument('--short', type=int, default=10)
    parser.add_argument('--long', type=int, default=30)
    args = parser.parse_args()
    main(args.ticker, args.short, args.long)
