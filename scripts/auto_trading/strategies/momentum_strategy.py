#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动量策略 (Momentum Strategy)

基于"强者恒强"的原理，买入近期表现强劲的股票。
动量策略在中国A股市场有较好的表现，特别是在牛市中。

参考文献：
- Jegadeesh and Titman (1993) "Returns to Buying Winners and Selling Losers"
- 国内研究显示A股市场存在显著的中期动量效应（1-12个月）
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class MomentumStrategy:
    """
    动量策略

    参数:
        lookback_period: 回溯期（计算动量的天数，默认20日）
        holding_period: 持有期（默认5日）
        universe: 股票池
    """

    def __init__(self, lookback_period: int = 20, holding_period: int = 5,
                 universe: Optional[List[str]] = None):
        self.lookback_period = lookback_period
        self.holding_period = holding_period
        self.universe = universe or []
        self.name = f"Momentum_{lookback_period}d"

    def calculate_momentum(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算动量指标

        参数:
            data: DataFrame with columns ['code', 'date', 'close', 'volume']

        返回:
            DataFrame with momentum metrics
        """
        momentum_data = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].sort_values('date').copy()

            if len(stock_data) < self.lookback_period + 1:
                continue

            # 计算收益率
            stock_data['return_1d'] = stock_data['close'].pct_change()

            # 计算多期动量
            stock_data['momentum_5d'] = stock_data['close'].pct_change(5)
            stock_data['momentum_10d'] = stock_data['close'].pct_change(10)
            stock_data['momentum_20d'] = stock_data['close'].pct_change(20)

            # 计算波动率（用于风险调整）
            stock_data['volatility'] = stock_data['return_1d'].rolling(
                window=self.lookback_period, min_periods=10
            ).std()

            # 计算成交量动量
            stock_data['volume_momentum'] = stock_data['volume'].pct_change(5)

            # 计算风险调整后的动量（类似夏普比率）
            stock_data['risk_adj_momentum'] = (
                stock_data['momentum_20d'] /
                (stock_data['volatility'] * np.sqrt(self.lookback_period))
            )

            # 计算趋势强度（连续上涨天数）
            stock_data['is_up'] = (stock_data['return_1d'] > 0).astype(int)
            stock_data['trend_strength'] = stock_data['is_up'].rolling(
                window=10, min_periods=5
            ).sum()

            momentum_data.append(stock_data)

        if momentum_data:
            return pd.concat(momentum_data, ignore_index=True)
        else:
            return pd.DataFrame()

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算动量信号

        参数:
            data: DataFrame with columns ['code', 'date', 'close', 'volume']

        返回:
            DataFrame with columns ['code', 'date', 'signal', 'score']
        """
        # 计算动量指标
        momentum_data = self.calculate_momentum(data)

        if momentum_data.empty:
            return pd.DataFrame(columns=['code', 'date', 'signal', 'score'])

        signals = []

        for date in momentum_data['date'].unique():
            daily_data = momentum_data[momentum_data['date'] == date].copy()

            # 过滤掉缺失值
            daily_data = daily_data.dropna(subset=['momentum_20d', 'risk_adj_momentum'])

            if len(daily_data) == 0:
                continue

            # 计算综合动量评分
            # 1. 标准化各个动量指标
            for col in ['momentum_5d', 'momentum_10d', 'momentum_20d', 'risk_adj_momentum']:
                if col in daily_data.columns:
                    mean_val = daily_data[col].mean()
                    std_val = daily_data[col].std()
                    if std_val > 0:
                        daily_data[f'{col}_norm'] = (daily_data[col] - mean_val) / std_val
                    else:
                        daily_data[f'{col}_norm'] = 0

            # 2. 综合评分（加权平均）
            daily_data['momentum_score'] = (
                0.2 * daily_data['momentum_5d_norm'] +
                0.3 * daily_data['momentum_10d_norm'] +
                0.3 * daily_data['momentum_20d_norm'] +
                0.2 * daily_data['risk_adj_momentum_norm']
            )

            # 3. 考虑成交量确认
            daily_data['volume_confirm'] = (daily_data['volume_momentum'] > 0).astype(int)
            daily_data['momentum_score'] = daily_data['momentum_score'] + 0.5 * daily_data['volume_confirm']

            # 4. 考虑趋势强度
            daily_data['momentum_score'] = (
                daily_data['momentum_score'] +
                0.1 * (daily_data['trend_strength'] - 5)
            )

            # 5. 转换为0-100分
            min_score = daily_data['momentum_score'].min()
            max_score = daily_data['momentum_score'].max()
            if max_score > min_score:
                daily_data['score'] = (
                    (daily_data['momentum_score'] - min_score) /
                    (max_score - min_score) * 100
                )
            else:
                daily_data['score'] = 50

            # 6. 生成信号
            # 选择评分最高的前30%作为买入信号
            threshold = daily_data['score'].quantile(0.7)
            daily_data['signal'] = 0
            daily_data.loc[daily_data['score'] >= threshold, 'signal'] = 1

            # 负动量且评分低的标记为卖出
            daily_data.loc[
                (daily_data['momentum_20d'] < -0.05) & (daily_data['score'] < 30),
                'signal'
            ] = -1

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
        start_date = target_date - timedelta(days=self.lookback_period * 2)

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
                 transaction_cost: float = 0.002) -> Dict:
        """
        回测动量策略

        参数:
            data: 历史数据
            date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            topk: 每次选择前K个股票
            transaction_cost: 交易成本（双边）

        返回:
            回测结果字典
        """
        # 获取交易日期列表
        trade_dates = sorted(data['date'].unique())
        trade_dates = [d for d in trade_dates if start_date <= d <= end_date]

        # 初始化
        capital = initial_capital
        positions = {}  # {code: {'shares': n, 'cost': price, 'entry_date': date}}
        portfolio_values = []
        trades = []

        for i, date in enumerate(trade_dates):
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

            # 卖出持有超过holding_period天的股票
            to_sell = []
            for code in positions:
                entry_idx = trade_dates.index(positions[code]['entry_date'])
                if i - entry_idx >= self.holding_period:
                    to_sell.append(code)

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
                        'value': proceeds
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
            position_value = sum(
                positions[code]['shares'] * current_prices.get(code, positions[code]['cost'])
                for code in positions
            )
            total_value = capital + position_value

            # 计算每个新仓位的目标资金
            current_position_count = len(positions)
            available_slots = topk - current_position_count

            if available_slots > 0 and len(buy_candidates) > 0:
                # 为新仓位分配资金
                # 目标是让所有仓位等权重
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
                                        'cost': buy_price,
                                        'entry_date': date
                                    }

                                    trades.append({
                                        'date': date,
                                        'code': code,
                                        'action': 'buy',
                                        'price': buy_price,
                                        'shares': shares_to_buy,
                                        'value': cost
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
    print(f"动量策略模块 - {MomentumStrategy().name}")
    print("强者恒强：买入近期表现强劲的股票")
