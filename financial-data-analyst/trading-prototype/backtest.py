import argparse
import yfinance as yf
import pandas as pd
import backtrader as bt
from strategy import SmaCross

# Visualization and reporting
import matplotlib.pyplot as plt
import os
from datetime import datetime
import csv


def run_backtest(ticker: str, start: str, end: str, cash: float = 100, commission: float = 0.002, slippage: float = 0.001):
    print(f"Downloading {ticker} from {start} to {end}...")
    df = yf.download(ticker, start=start, end=end, progress=False)
    if df.empty:
        raise SystemExit("No data downloaded. Check ticker or date range.")

    df.index = pd.to_datetime(df.index)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    # Set commission (fractional, e.g., 0.002 = 0.2%)
    cerebro.broker.setcommission(commission=commission)
    # Pass slippage into the strategy which simulates execution at limit prices adjusted by slippage
    cerebro.addstrategy(SmaCross, slippage=slippage)

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f}")
    results = cerebro.run()
    print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f}")

    # Reporting totals from the strategy (if provided)
    try:
        strat = results[0]
        total_commission = getattr(strat, 'total_commission', 0.0)
        total_slippage = getattr(strat, 'total_slippage', 0.0)
        trade_count = getattr(strat, 'trade_count', 0)
        total_volume = getattr(strat, 'total_volume', 0)

        print('\n--- Trade Summary ---')
        print(f'Trades closed: {trade_count}')
        print(f'Total commission paid: {total_commission:.4f}')
        print(f'Total slippage cost: {total_slippage:.4f}')
        print(f'Total volume traded: {total_volume}')
        print('---------------------\n')

        # Prepare paths
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        results_dir = 'financial-data-analyst/trading-prototype'
        os.makedirs(results_dir, exist_ok=True)
        base = f"{results_dir}/results_{ticker.replace('/','_')}_{timestamp}"

        exec_log = getattr(strat, 'exec_log', [])
        trade_summaries = getattr(strat, 'trade_summaries', [])
        portfolio_history = getattr(strat, 'portfolio_history', [])

        # Write execution log CSV
        if exec_log:
            exec_file = base + '_executions.csv'
            try:
                with open(exec_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['timestamp','side','price','size','commission','slippage_cost'])
                    writer.writeheader()
                    for row in exec_log:
                        writer.writerow(row)
                print(f'Execution log saved to {exec_file}')
            except Exception as ew:
                print('Failed to write execution log:', ew)

        # Write trade summary CSV
        if trade_summaries:
            summary_file = base + '_trades.csv'
            try:
                with open(summary_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['close_date','pnl','pnl_comm'])
                    writer.writeheader()
                    for row in trade_summaries:
                        writer.writerow(row)
                print(f'Trade summaries saved to {summary_file}')
            except Exception as sw:
                print('Failed to write trade summary file:', sw)

        # Create equity curve plot if portfolio history exists
        report_file = base + '_report.html'
        try:
            if portfolio_history:
                ph_df = pd.DataFrame(portfolio_history)
                # try parse timestamps if possible
                try:
                    ph_df['timestamp'] = pd.to_datetime(ph_df['timestamp'])
                except Exception:
                    pass

                plt.figure(figsize=(10,4))
                plt.plot(ph_df['timestamp'], ph_df['value'], marker='.', linewidth=1)
                plt.title(f'Equity Curve - {ticker}')
                plt.xlabel('Date')
                plt.ylabel('Portfolio Value')
                plt.grid(True)

                png_file = base + '_equity.png'
                plt.tight_layout()
                plt.savefig(png_file)
                plt.close()
                print(f'Equity curve saved to {png_file}')

                # Generate HTML report including links and embedded image
                try:
                    with open(report_file, 'w') as f:
                        f.write('<html><head><meta charset="utf-8"><title>Backtest Report</title></head><body>')
                        f.write(f'<h1>Backtest Report - {ticker}</h1>')
                        f.write(f'<p>Start: {start} &nbsp; End: {end} &nbsp; Starting Cash: {cash}</p>')
                        f.write('<h2>Summary</h2>')
                        f.write(f'<p>Final Portfolio Value: {cerebro.broker.getvalue():.2f}</p>')
                        f.write(f'<p>Trades closed: {trade_count}</p>')
                        f.write(f'<p>Total commission paid: {total_commission:.4f}</p>')
                        f.write(f'<p>Total slippage cost: {total_slippage:.4f}</p>')
                        f.write('<h2>Equity Curve</h2>')
                        f.write(f'<img src="{os.path.basename(png_file)}" alt="equity" style="max-width:100%;height:auto;">')

                        if exec_log:
                            f.write('<h2>Execution Log</h2>')
                            f.write(f'<p><a href="{os.path.basename(exec_file)}">Download executions CSV</a></p>')
                        if trade_summaries:
                            f.write('<h2>Trade Summaries</h2>')
                            f.write(f'<p><a href="{os.path.basename(summary_file)}">Download trade summaries CSV</a></p>')

                        f.write('</body></html>')
                    # Copy image and csvs next to the html for relative links
                    try:
                        # Ensure files are copied into same directory with base name
                        # Nothing needed because files already saved there with base prefix
                        print(f'Report saved to {report_file}')
                    except Exception:
                        pass
                except Exception as he:
                    print('Failed to write HTML report:', he)
            else:
                print('No portfolio history to plot')
        except Exception as e:
            print('Failed to generate report:', e)

    except Exception as e:
        print('No strategy metrics available:', e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--cash', type=float, default=100)
    parser.add_argument('--commission', type=float, default=0.002, help='broker commission as fraction (e.g., 0.002 for 0.2%)')
    parser.add_argument('--slippage', type=float, default=0.001, help='per-trade slippage fraction (e.g., 0.001 for 0.1%)')
    args = parser.parse_args()

    run_backtest(args.ticker, args.start, args.end, args.cash, args.commission, args.slippage)
