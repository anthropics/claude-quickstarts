import backtrader as bt

class SmaCross(bt.Strategy):
    params = dict(short_period=10, long_period=30, stake=10, slippage=0.001)

    def __init__(self):
        self.sma_short = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.p.short_period)
        self.sma_long = bt.indicators.SimpleMovingAverage(self.datas[0], period=self.p.long_period)
        self.crossover = bt.indicators.CrossOver(self.sma_short, self.sma_long)

        # Metrics for reporting
        self.total_commission = 0.0
        self.total_slippage = 0.0
        self.total_volume = 0
        self.trade_count = 0
        self.portfolio_history = []

    def log(self, txt):
        print(txt)

    def next(self):
        # If not in the market, look for a buy signal
        if not self.position:
            if self.crossover > 0:
                self.log(f"BUY  {self.datas[0].datetime.date(0)} Close={self.datas[0].close[0]:.2f}")
                self.buy(size=self.p.stake, price=self.datas[0].close[0] * (1 + self.p.slippage), exectype=bt.Order.Limit)
        else:
            # In the market: exit when crossover goes negative
            if self.crossover < 0:
                self.log(f"SELL {self.datas[0].datetime.date(0)} Close={self.datas[0].close[0]:.2f}")
                self.close(price=self.datas[0].close[0] * (1 - self.p.slippage), exectype=bt.Order.Limit)

        # Record portfolio value for equity curve
        try:
            ts = getattr(self.datas[0].datetime, 'date')(0).isoformat()
        except Exception:
            try:
                ts = str(self.datas[0].datetime.datetime(0))
            except Exception:
                ts = ''
        try:
            value = float(self.broker.getvalue())
        except Exception:
            value = 0.0
        self.portfolio_history.append({'timestamp': ts, 'value': value})

    def notify_order(self, order):
        # Called on order status changes; capture executed details for reporting
        if order.status == bt.Order.Completed:
            executed = getattr(order, 'executed', None)
            if executed:
                price = getattr(executed, 'price', 0.0) or 0.0
                size = getattr(executed, 'size', 0) or 0
                comm = getattr(executed, 'comm', 0.0) or 0.0

                # Use current close as reference for slippage calculation
                try:
                    current_close = float(self.datas[0].close[0])
                except Exception:
                    current_close = price

                slippage_cost = abs(price - current_close) * abs(size)

                self.total_slippage += slippage_cost
                self.total_commission += comm
                self.total_volume += abs(size)

                # Determine buy/sell
                try:
                    side = 'buy' if order.isbuy() else 'sell'
                except Exception:
                    side = 'buy' if size > 0 else 'sell'

                ts = None
                try:
                    ts = getattr(self.datas[0].datetime, 'date')(0).isoformat()
                except Exception:
                    try:
                        ts = str(self.datas[0].datetime.datetime(0))
                    except Exception:
                        ts = ''

                entry = {
                    'timestamp': ts,
                    'side': side,
                    'price': float(price),
                    'size': float(size),
                    'commission': float(comm),
                    'slippage_cost': float(slippage_cost),
                }

                # Initialize exec_log if needed
                if not hasattr(self, 'exec_log'):
                    self.exec_log = []
                self.exec_log.append(entry)

                self.log(f"Order executed: {side} price={price:.2f} size={size} comm={comm:.4f} slippage_cost={slippage_cost:.4f}")

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_count += 1
            # Record trade summary
            try:
                close_ts = getattr(self.datas[0].datetime, 'date')(0).isoformat()
            except Exception:
                close_ts = ''

            summary = {
                'close_date': close_ts,
                'pnl': float(trade.pnl) if hasattr(trade, 'pnl') else 0.0,
                'pnl_comm': float(trade.pnlcomm) if hasattr(trade, 'pnlcomm') else 0.0,
            }

            if not hasattr(self, 'trade_summaries'):
                self.trade_summaries = []
            self.trade_summaries.append(summary)

            self.log(f"Trade closed, PnL Gross {trade.pnl:.2f}")

    def stop(self):
        # Summary when strategy ends
        self.log(f"Total trades: {self.trade_count}")
        self.log(f"Total commission: {self.total_commission:.4f}")
        self.log(f"Total slippage cost: {self.total_slippage:.4f}")
        self.log(f"Total volume traded: {self.total_volume}")
        # Ensure exec_log and trade_summaries exist
        if not hasattr(self, 'exec_log'):
            self.exec_log = []
        if not hasattr(self, 'trade_summaries'):
            self.trade_summaries = []
