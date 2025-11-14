#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双均线策略 (Dual Moving Average Strategy)

经典的技术分析策略，当短期均线向上穿过长期均线时买入（金叉），
当短期均线向下穿过长期均线时卖出（死叉）。

这是最经典、应用最广泛的量化策略之一。
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class DualMAStrategy:
    """
    双均线策略

    参数:
        short_window: 短期均线窗口期（默认5日）
        long_window: 长期均线窗口期（默认20日）
        universe: 股票池
    """

    def __init__(self, short_window: int = 5, long_window: int = 20,
                 universe: Optional[List[str]] = None):
        self.short_window = short_window
        self.long_window = long_window
        self.universe = universe or []
        self.name = f"DualMA_{short_window}_{long_window}"

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算双均线信号

        参数:
            data: DataFrame with columns ['code', 'date', 'close', 'volume']

        返回:
            DataFrame with columns ['code', 'date', 'signal', 'score']
            - signal: 1 (买入), -1 (卖出), 0 (持有)
            - score: 信号强度 (0-100)
        """
        signals = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].sort_values('date').copy()

            if len(stock_data) < self.long_window:
                continue

            # 计算短期和长期均线
            stock_data['ma_short'] = stock_data['close'].rolling(
                window=self.short_window, min_periods=1
            ).mean()
            stock_data['ma_long'] = stock_data['close'].rolling(
                window=self.long_window, min_periods=1
            ).mean()

            # 计算均线差值百分比
            stock_data['ma_diff_pct'] = (
                (stock_data['ma_short'] - stock_data['ma_long']) / stock_data['ma_long'] * 100
            )

            # 检测金叉和死叉
            stock_data['prev_ma_short'] = stock_data['ma_short'].shift(1)
            stock_data['prev_ma_long'] = stock_data['ma_long'].shift(1)

            # 金叉: 前一日短均线<长均线，当日短均线>长均线
            golden_cross = (
                (stock_data['prev_ma_short'] < stock_data['prev_ma_long']) &
                (stock_data['ma_short'] > stock_data['ma_long'])
            )

            # 死叉: 前一日短均线>长均线，当日短均线<长均线
            death_cross = (
                (stock_data['prev_ma_short'] > stock_data['prev_ma_long']) &
                (stock_data['ma_short'] < stock_data['ma_long'])
            )

            # 生成信号
            stock_data['signal'] = 0
            stock_data.loc[golden_cross, 'signal'] = 1  # 买入
            stock_data.loc[death_cross, 'signal'] = -1  # 卖出

            # 持续持有信号: 短均线持续在长均线之上
            持有 = (
                (stock_data['signal'] == 0) &
                (stock_data['ma_short'] > stock_data['ma_long'])
            )
            stock_data.loc[持有, 'signal'] = 1

            # 计算信号强度 (基于均线差值的百分比)
            stock_data['score'] = 50 + stock_data['ma_diff_pct'].clip(-50, 50)
            stock_data['score'] = stock_data['score'].clip(0, 100)

            # 添加成交量确认
            stock_data['volume_ma'] = stock_data['volume'].rolling(
                window=self.short_window, min_periods=1
            ).mean()
            stock_data['volume_ratio'] = stock_data['volume'] / stock_data['volume_ma']

            # 如果金叉时成交量放大，提高评分
            volume_boost = (golden_cross & (stock_data['volume_ratio'] > 1.5))
            stock_data.loc[volume_boost, 'score'] = stock_data.loc[volume_boost, 'score'] * 1.2
            stock_data['score'] = stock_data['score'].clip(0, 100)

            signals.append(stock_data[['code', 'date', 'signal', 'score']])

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
        start_date = target_date - timedelta(days=self.long_window * 2)

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
        回测双均线策略

        参数:
            data: 历史数据
            start_date: 回测开始日期
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

            # 生成信号
            signals_result = self.generate_daily_signals(data, date, topk)
            signals = signals_result['signals']

            if signals.empty:
                continue

            # 获取买入候选
            buy_candidates = set(signals['code'].tolist())

            # 卖出不在候选列表中的股票
            to_sell = [code for code in positions if code not in buy_candidates]

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

            # 买入新股票（等权重）
            position_value = sum(
                positions[code]['shares'] * current_prices.get(code, positions[code]['cost'])
                for code in positions
            )
            total_value = capital + position_value

            # 为每个持仓分配资金
            target_count = min(topk, len(buy_candidates))
            if target_count > 0:
                target_per_stock = total_value / target_count

                for code in buy_candidates:
                    if code in current_prices:
                        buy_price = current_prices[code]

                        if code in positions:
                            # 调整现有持仓
                            current_value = positions[code]['shares'] * buy_price
                            if current_value < target_per_stock * 0.9:  # 需要加仓
                                diff_value = target_per_stock - current_value
                                if diff_value <= capital:
                                    shares_to_buy = int(diff_value / buy_price / (1 + transaction_cost))
                                    if shares_to_buy > 0:
                                        cost = shares_to_buy * buy_price * (1 + transaction_cost)
                                        capital -= cost
                                        positions[code]['shares'] += shares_to_buy

                                        trades.append({
                                            'date': date,
                                            'code': code,
                                            'action': 'buy',
                                            'price': buy_price,
                                            'shares': shares_to_buy,
                                            'value': cost
                                        })
                        else:
                            # 新买入
                            if target_per_stock <= capital:
                                shares_to_buy = int(target_per_stock / buy_price / (1 + transaction_cost))
                                if shares_to_buy > 0:
                                    cost = shares_to_buy * buy_price * (1 + transaction_cost)
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
    print(f"双均线策略模块 - {DualMAStrategy().name}")
    print("经典技术分析策略：金叉买入，死叉卖出")
