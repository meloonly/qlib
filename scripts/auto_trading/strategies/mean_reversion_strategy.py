#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均值回归策略 (Mean Reversion Strategy)

基于"物极必反"的原理，当股价偏离其均值过多时，
预期会回归到均值水平。适合在震荡市中使用。

使用布林带、RSI等指标识别超买超卖状态。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class MeanReversionStrategy:
    """
    均值回归策略

    参数:
        window: 均值计算窗口期（默认20日）
        std_multiplier: 标准差倍数（布林带宽度，默认2）
        rsi_period: RSI周期（默认14日）
        universe: 股票池
    """

    def __init__(self, window: int = 20, std_multiplier: float = 2.0,
                 rsi_period: int = 14, universe: Optional[List[str]] = None):
        self.window = window
        self.std_multiplier = std_multiplier
        self.rsi_period = rsi_period
        self.universe = universe or []
        self.name = f"MeanReversion_{window}d"

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_bollinger_bands(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算布林带和相关指标

        参数:
            data: DataFrame with stock data

        返回:
            DataFrame with Bollinger Bands
        """
        result = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].sort_values('date').copy()

            if len(stock_data) < self.window:
                continue

            # 计算中轨（移动平均）
            stock_data['bb_middle'] = stock_data['close'].rolling(
                window=self.window, min_periods=1
            ).mean()

            # 计算标准差
            stock_data['bb_std'] = stock_data['close'].rolling(
                window=self.window, min_periods=1
            ).std()

            # 计算上下轨
            stock_data['bb_upper'] = (
                stock_data['bb_middle'] + self.std_multiplier * stock_data['bb_std']
            )
            stock_data['bb_lower'] = (
                stock_data['bb_middle'] - self.std_multiplier * stock_data['bb_std']
            )

            # 计算布林带宽度（波动率指标）
            stock_data['bb_width'] = (
                (stock_data['bb_upper'] - stock_data['bb_lower']) / stock_data['bb_middle']
            )

            # 计算价格在布林带中的位置 (0-1)
            stock_data['bb_position'] = (
                (stock_data['close'] - stock_data['bb_lower']) /
                (stock_data['bb_upper'] - stock_data['bb_lower'])
            )

            # 计算价格偏离中轨的百分比
            stock_data['price_deviation'] = (
                (stock_data['close'] - stock_data['bb_middle']) / stock_data['bb_middle']
            )

            # 计算RSI
            stock_data['rsi'] = self.calculate_rsi(stock_data['close'], self.rsi_period)

            # 计算价格变化率
            stock_data['price_change_pct'] = stock_data['close'].pct_change(5)

            result.append(stock_data)

        if result:
            return pd.concat(result, ignore_index=True)
        else:
            return pd.DataFrame()

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算均值回归信号

        参数:
            data: DataFrame with columns ['code', 'date', 'close', 'volume']

        返回:
            DataFrame with columns ['code', 'date', 'signal', 'score']
        """
        # 计算布林带指标
        bb_data = self.calculate_bollinger_bands(data)

        if bb_data.empty:
            return pd.DataFrame(columns=['code', 'date', 'signal', 'score'])

        signals = []

        for date in bb_data['date'].unique():
            daily_data = bb_data[bb_data['date'] == date].copy()

            # 过滤掉缺失值
            daily_data = daily_data.dropna(
                subset=['bb_position', 'rsi', 'price_deviation']
            )

            if len(daily_data) == 0:
                continue

            # 初始化信号和评分
            daily_data['signal'] = 0
            daily_data['score'] = 50.0

            # === 买入信号（超卖） ===
            # 1. 价格触及或跌破下轨
            oversold_bb = daily_data['bb_position'] < 0.2

            # 2. RSI超卖
            oversold_rsi = daily_data['rsi'] < 30

            # 3. 价格大幅下跌
            price_drop = daily_data['price_change_pct'] < -0.05

            # 综合超卖信号
            buy_signal = oversold_bb | (oversold_rsi & price_drop)

            # 计算买入评分
            daily_data.loc[buy_signal, 'score'] = (
                70 +
                20 * (1 - daily_data.loc[buy_signal, 'bb_position']) +  # 距离下轨越近评分越高
                10 * (50 - daily_data.loc[buy_signal, 'rsi']) / 50  # RSI越低评分越高
            )
            daily_data.loc[buy_signal, 'signal'] = 1

            # === 卖出信号（超买） ===
            # 1. 价格触及或突破上轨
            overbought_bb = daily_data['bb_position'] > 0.8

            # 2. RSI超买
            overbought_rsi = daily_data['rsi'] > 70

            # 3. 价格大幅上涨
            price_surge = daily_data['price_change_pct'] > 0.05

            # 综合超买信号
            sell_signal = overbought_bb | (overbought_rsi & price_surge)

            # 计算卖出评分（低分表示建议卖出）
            daily_data.loc[sell_signal, 'score'] = (
                30 -
                20 * (daily_data.loc[sell_signal, 'bb_position'] - 0.5) -  # 距离上轨越近评分越低
                10 * (daily_data.loc[sell_signal, 'rsi'] - 50) / 50  # RSI越高评分越低
            )
            daily_data.loc[sell_signal, 'signal'] = -1

            # === 持有信号（价格在合理区间） ===
            # 价格在中轨附近，保持持有
            hold_signal = (
                (~buy_signal) & (~sell_signal) &
                (daily_data['bb_position'] > 0.3) &
                (daily_data['bb_position'] < 0.7)
            )
            daily_data.loc[hold_signal, 'score'] = 50

            # === 额外的风险调整 ===
            # 1. 考虑布林带宽度（波动率）
            # 低波动时，均值回归效果更好
            low_volatility = daily_data['bb_width'] < daily_data['bb_width'].quantile(0.3)
            daily_data.loc[low_volatility & buy_signal, 'score'] += 5

            # 高波动时，降低信心
            high_volatility = daily_data['bb_width'] > daily_data['bb_width'].quantile(0.7)
            daily_data.loc[high_volatility, 'score'] -= 5

            # 2. 确保评分在0-100之间
            daily_data['score'] = daily_data['score'].clip(0, 100)

            signals.append(daily_data[['code', 'date', 'signal', 'score']])

        if signals:
            return pd.concat(signals, ignore_index=True)
        else:
            return pd.DataFrame(columns=['code', 'date', 'signal', 'score'])

    def generate_daily_signals(self, data: pd.DataFrame, date: str,
                              topk: int = 30) -> Dict:
        """
        生成指定日期的交易信号

        参数:
            data: 历史数据
            date: 目标日期
            topk: 选择前K个股票

        返回:
            {'date': date, 'signals': DataFrame with top stocks}
        """
        # 确保有足够的历史数据
        target_date = pd.to_datetime(date)
        start_date = target_date - timedelta(days=self.window * 2)

        # 过滤数据
        filtered_data = data[
            (pd.to_datetime(data['date']) >= start_date) &
            (pd.to_datetime(data['date']) <= target_date)
        ].copy()

        # 计算信号
        all_signals = self.calculate_signals(filtered_data)

        # 获取目标日期的信号
        daily_signals = all_signals[all_signals['date'] == date].copy()

        if daily_signals.empty:
            return {'date': date, 'signals': pd.DataFrame()}

        # 只保留买入信号
        buy_signals = daily_signals[daily_signals['signal'] > 0].copy()

        # 按评分排序，选择前topk
        buy_signals = buy_signals.sort_values('score', ascending=False).head(topk)

        return {
            'date': date,
            'signals': buy_signals,
            'strategy': self.name
        }

    def backtest(self, data: pd.DataFrame, start_date: str, end_date: str,
                 initial_capital: float = 100000, topk: int = 30,
                 transaction_cost: float = 0.002,
                 take_profit: float = 0.05, stop_loss: float = 0.03) -> Dict:
        """
        回测均值回归策略

        参数:
            data: 历史数据
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            topk: 每次选择前K个股票
            transaction_cost: 交易成本（双边）
            take_profit: 止盈阈值（默认5%）
            stop_loss: 止损阈值（默认3%）

        返回:
            回测结果字典
        """
        # 获取交易日期列表
        trade_dates = sorted(data['date'].unique())
        trade_dates = [d for d in trade_dates if start_date <= d <= end_date]

        # 初始化
        capital = initial_capital
        positions = {}  # {code: {'shares': n, 'cost': price}}
        portfolio_values = []
        trades = []

        for date in trade_dates:
            # 计算当前持仓市值
            current_prices = data[data['date'] == date].set_index('code')['close'].to_dict()

            position_value = sum(
                positions[code]['shares'] * current_prices.get(code, positions[code]['cost'])
                for code in positions
            )
            total_value = capital + position_value

            portfolio_values.append({
                'date': date,
                'total_value': total_value,
                'cash': capital,
                'position_value': position_value
            })

            # 检查止盈止损
            to_sell = []
            for code in positions:
                if code in current_prices:
                    current_price = current_prices[code]
                    cost_price = positions[code]['cost']
                    profit_pct = (current_price - cost_price) / cost_price

                    # 止盈或止损
                    if profit_pct >= take_profit or profit_pct <= -stop_loss:
                        to_sell.append(code)

            # 执行止盈止损卖出
            for code in to_sell:
                if code in current_prices:
                    sell_price = current_prices[code]
                    shares = positions[code]['shares']
                    proceeds = shares * sell_price * (1 - transaction_cost)
                    capital += proceeds

                    trades.append({
                        'date': date,
                        'code': code,
                        'action': 'sell',
                        'price': sell_price,
                        'shares': shares,
                        'value': proceeds,
                        'reason': 'take_profit' if (sell_price - positions[code]['cost']) / positions[code]['cost'] >= take_profit else 'stop_loss'
                    })

                    del positions[code]

            # 生成信号
            signals_result = self.generate_daily_signals(data, date, topk)
            signals = signals_result['signals']

            if signals.empty:
                continue

            # 获取买入候选（不包括已持有的）
            buy_candidates = [
                code for code in signals['code'].tolist()
                if code not in positions
            ]

            # 等权重买入
            current_position_count = len(positions)
            available_slots = topk - current_position_count

            if available_slots > 0 and len(buy_candidates) > 0:
                # 计算每个新仓位的目标资金
                target_per_stock = total_value / min(topk, current_position_count + len(buy_candidates))

                for code in buy_candidates[:available_slots]:
                    if code in current_prices:
                        buy_price = current_prices[code]
                        target_value = min(target_per_stock, capital * 0.95)  # 保留5%现金

                        if target_value > 0:
                            shares_to_buy = int(target_value / buy_price / (1 + transaction_cost))
                            if shares_to_buy > 0:
                                cost = shares_to_buy * buy_price * (1 + transaction_cost)
                                if cost <= capital:
                                    capital -= cost
                                    positions[code] = {
                                        'shares': shares_to_buy,
                                        'cost': buy_price
                                    }

                                    trades.append({
                                        'date': date,
                                        'code': code,
                                        'action': 'buy',
                                        'price': buy_price,
                                        'shares': shares_to_buy,
                                        'value': cost,
                                        'reason': 'oversold'
                                    })

        # 计算最终市值
        final_prices = data[data['date'] == trade_dates[-1]].set_index('code')['close'].to_dict()
        final_position_value = sum(
            positions[code]['shares'] * final_prices.get(code, positions[code]['cost'])
            for code in positions
        )
        final_total_value = capital + final_position_value

        # 计算绩效指标
        portfolio_df = pd.DataFrame(portfolio_values)
        portfolio_df['returns'] = portfolio_df['total_value'].pct_change()

        total_return = (final_total_value - initial_capital) / initial_capital
        annual_return = (1 + total_return) ** (252 / len(trade_dates)) - 1 if len(trade_dates) > 0 else 0
        volatility = portfolio_df['returns'].std() * np.sqrt(252)
        sharpe_ratio = annual_return / volatility if volatility > 0 else 0

        cummax = portfolio_df['total_value'].cummax()
        drawdown = (portfolio_df['total_value'] - cummax) / cummax
        max_drawdown = drawdown.min()

        return {
            'strategy': self.name,
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': initial_capital,
            'final_value': final_total_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': len(trades),
            'portfolio_history': portfolio_df,
            'trades': pd.DataFrame(trades) if trades else pd.DataFrame()
        }


if __name__ == '__main__':
    # 简单测试
    print(f"均值回归策略模块 - {MeanReversionStrategy().name}")
    print("物极必反：买入超卖，卖出超买")
