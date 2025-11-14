#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha101 因子策略

基于 WorldQuant 发布的 101 个 Alpha 因子（2015）。
这些因子是通过大量数据挖掘和机器学习验证的量化指标。

本实现选择了其中最经典和有效的10个因子进行组合。

参考文献:
- WorldQuant (2015) "101 Formulaic Alphas"
- 这些因子在全球市场（包括中国A股）都有较好的表现
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class Alpha101Strategy:
    """
    Alpha101 多因子策略

    实现 WorldQuant Alpha101 中的经典因子
    """

    def __init__(self, universe: Optional[List[str]] = None):
        self.universe = universe or []
        self.name = "Alpha101_MultiFactors"

    @staticmethod
    def ts_rank(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
        """时序排名"""
        return df.rolling(window=window, min_periods=window).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1]
        )

    @staticmethod
    def ts_sum(df: pd.DataFrame, window: int) -> pd.DataFrame:
        """时序求和"""
        return df.rolling(window=window, min_periods=window).sum()

    @staticmethod
    def ts_mean(df: pd.DataFrame, window: int) -> pd.DataFrame:
        """时序均值"""
        return df.rolling(window=window, min_periods=window).mean()

    @staticmethod
    def ts_std(df: pd.DataFrame, window: int) -> pd.DataFrame:
        """时序标准差"""
        return df.rolling(window=window, min_periods=window).std()

    @staticmethod
    def ts_corr(x: pd.DataFrame, y: pd.DataFrame, window: int) -> pd.DataFrame:
        """时序相关性"""
        return x.rolling(window=window, min_periods=window).corr(y)

    @staticmethod
    def delta(df: pd.DataFrame, period: int = 1) -> pd.DataFrame:
        """差分"""
        return df.diff(period)

    @staticmethod
    def delay(df: pd.DataFrame, period: int = 1) -> pd.DataFrame:
        """延迟"""
        return df.shift(period)

    def alpha_001(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#1: rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5))
        当收益为负时用波动率，否则用收盘价
        """
        returns = data['close'].pct_change()
        stddev = returns.rolling(20, min_periods=20).std()

        inner = pd.DataFrame({
            'neg': stddev.where(returns < 0, data['close'])
        })
        power = inner['neg'] ** 2
        result = self.ts_rank(power, 5)
        return result.fillna(0.5)

    def alpha_002(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#2: (-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))
        成交量变化与价格变化的负相关
        """
        volume_delta = np.log(data['volume']).diff(2)
        price_change = (data['close'] - data['open']) / data['open']

        volume_rank = volume_delta.rolling(10).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])
        price_rank = price_change.rolling(10).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1])

        corr = volume_rank.rolling(6, min_periods=6).corr(price_rank)
        return (-1 * corr).fillna(0.5)

    def alpha_006(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#6: (-1 * correlation(open, volume, 10))
        开盘价与成交量的负相关
        """
        corr = data['open'].rolling(10, min_periods=10).corr(data['volume'])
        return (-1 * corr).fillna(0.5)

    def alpha_012(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#12: sign(delta(volume, 1)) * (-1 * delta(close, 1))
        成交量方向与价格变化的负相关
        """
        volume_sign = np.sign(data['volume'].diff(1))
        price_delta = data['close'].diff(1)
        return (volume_sign * (-1) * price_delta).fillna(0)

    def alpha_017(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#17: (((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) *
                   rank(ts_rank((volume / adv20), 5)))
        结合价格趋势和成交量
        """
        close_rank = self.ts_rank(data['close'], 10)
        price_delta2 = data['close'].diff(1).diff(1)

        adv20 = data['volume'].rolling(20, min_periods=20).mean()
        volume_ratio = data['volume'] / adv20
        volume_rank = self.ts_rank(volume_ratio, 5)

        result = ((-1 * close_rank) * price_delta2 * volume_rank)
        return result.fillna(0)

    def alpha_019(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#19: ((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) *
                   (1 + rank((1 + sum(returns, 250)))))
        """
        close_diff = (data['close'] - data['close'].shift(7)) + data['close'].diff(7)
        returns = data['close'].pct_change()
        sum_returns = returns.rolling(250, min_periods=100).sum()

        result = (-1 * np.sign(close_diff) * (1 + sum_returns))
        return result.fillna(0)

    def alpha_021(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#21: 线性回归
        """
        mean_close = data['close'].rolling(8, min_periods=8).mean()
        cond1 = (mean_close + data['close'].rolling(8).std()) < mean_close.shift(1)
        cond2 = mean_close.shift(1) < (mean_close.shift(2))
        cond3 = (mean_close - data['close'].rolling(8).std()) < mean_close.shift(1)

        result = pd.Series(0, index=data.index)
        result[cond1 | cond2] = -1
        result[~(cond1 | cond2) & cond3] = 1

        return result

    def alpha_026(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#26: 成交量加权平均价格与收盘价的关系
        """
        vol_mean = data['volume'].rolling(20, min_periods=20).mean()
        corr = data['high'].rolling(5, min_periods=5).corr(vol_mean)

        result = -1 * corr.rank(pct=True)
        return result.fillna(0.5)

    def alpha_028(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#28: 3日价格变化率 - 成交量关系
        """
        price_change = (data['close'] - data['close'].shift(3)) / data['close'].shift(3)
        vol_change = (data['volume'] - data['volume'].shift(3)) / data['volume'].shift(3)

        result = price_change - vol_change
        return result.fillna(0)

    def alpha_033(self, data: pd.DataFrame) -> pd.Series:
        """
        Alpha#33: 开盘价/收盘价比率
        """
        result = -1 * (data['open'] / data['close'])
        return result.fillna(-1)

    def calculate_all_factors(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有Alpha因子

        参数:
            data: DataFrame for a single stock

        返回:
            DataFrame with all alpha factors
        """
        result = data[['code', 'date', 'close']].copy()

        try:
            result['alpha_001'] = self.alpha_001(data)
            result['alpha_002'] = self.alpha_002(data)
            result['alpha_006'] = self.alpha_006(data)
            result['alpha_012'] = self.alpha_012(data)
            result['alpha_017'] = self.alpha_017(data)
            result['alpha_019'] = self.alpha_019(data)
            result['alpha_021'] = self.alpha_021(data)
            result['alpha_026'] = self.alpha_026(data)
            result['alpha_028'] = self.alpha_028(data)
            result['alpha_033'] = self.alpha_033(data)
        except Exception as e:
            # 如果某个因子计算失败，填充默认值
            for i in [1, 2, 6, 12, 17, 19, 21, 26, 28, 33]:
                col = f'alpha_{i:03d}'
                if col not in result.columns:
                    result[col] = 0

        return result

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算交易信号

        参数:
            data: DataFrame with columns ['code', 'date', 'close', 'open', 'high', 'low', 'volume']

        返回:
            DataFrame with columns ['code', 'date', 'signal', 'score']
        """
        all_factors = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].sort_values('date').copy()

            if len(stock_data) < 250:  # 需要足够的历史数据
                continue

            # 计算因子
            factors = self.calculate_all_factors(stock_data)
            all_factors.append(factors)

        if not all_factors:
            return pd.DataFrame(columns=['code', 'date', 'signal', 'score'])

        all_factors_df = pd.concat(all_factors, ignore_index=True)

        # 计算综合得分
        signals = []
        alpha_cols = [col for col in all_factors_df.columns if col.startswith('alpha_')]

        for date in all_factors_df['date'].unique():
            daily_data = all_factors_df[all_factors_df['date'] == date].copy()

            # 对每个因子进行截面标准化
            for col in alpha_cols:
                mean_val = daily_data[col].mean()
                std_val = daily_data[col].std()
                if std_val > 0:
                    daily_data[f'{col}_norm'] = (daily_data[col] - mean_val) / std_val
                else:
                    daily_data[f'{col}_norm'] = 0

            # 计算综合得分（等权平均）
            norm_cols = [f'{col}_norm' for col in alpha_cols]
            daily_data['alpha_score'] = daily_data[norm_cols].mean(axis=1)

            # 转换为0-100分
            min_score = daily_data['alpha_score'].min()
            max_score = daily_data['alpha_score'].max()
            if max_score > min_score:
                daily_data['score'] = (
                    (daily_data['alpha_score'] - min_score) /
                    (max_score - min_score) * 100
                )
            else:
                daily_data['score'] = 50

            # 生成信号：选择得分最高的前30%
            threshold = daily_data['score'].quantile(0.7)
            daily_data['signal'] = 0
            daily_data.loc[daily_data['score'] >= threshold, 'signal'] = 1

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
        start_date = target_date - timedelta(days=365)  # 需要至少1年数据

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
                 rebalance_freq: int = 5) -> Dict:
        """
        回测Alpha101策略

        参数:
            data: 历史数据
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            topk: 每次选择前K个股票
            transaction_cost: 交易成本（双边）
            rebalance_freq: 调仓频率（天数）

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
        last_rebalance_idx = -rebalance_freq  # 初始触发调仓

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

            # 检查是否需要调仓
            if i - last_rebalance_idx < rebalance_freq:
                continue

            last_rebalance_idx = i

            # 生成信号
            signals_result = self.generate_daily_signals(data, date, topk)
            signals = signals_result['signals']

            if signals.empty:
                continue

            # 获取目标持仓
            target_codes = set(signals['code'].tolist())
            current_codes = set(positions.keys())

            # 卖出不在目标中的股票
            to_sell = current_codes - target_codes
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

            # 等权重分配资金
            total_value = capital + sum(
                positions[code]['shares'] * current_prices.get(code, positions[code]['cost'])
                for code in positions
            )

            target_per_stock = total_value / len(target_codes)

            # 调整持仓
            for code in target_codes:
                if code not in current_prices:
                    continue

                current_price = current_prices[code]

                if code in positions:
                    # 调整现有持仓
                    current_value = positions[code]['shares'] * current_price
                    diff_value = target_per_stock - current_value

                    if abs(diff_value) > target_per_stock * 0.1:  # 偏差超过10%才调整
                        if diff_value > 0:  # 加仓
                            shares_to_buy = int(diff_value / current_price / (1 + transaction_cost))
                            if shares_to_buy > 0:
                                cost = shares_to_buy * current_price * (1 + transaction_cost)
                                if cost <= capital:
                                    capital -= cost
                                    positions[code]['shares'] += shares_to_buy
                                    trades.append({
                                        'date': date,
                                        'code': code,
                                        'action': 'buy',
                                        'price': current_price,
                                        'shares': shares_to_buy,
                                        'value': cost
                                    })
                        else:  # 减仓
                            shares_to_sell = int(abs(diff_value) / current_price)
                            if shares_to_sell > 0:
                                shares_to_sell = min(shares_to_sell, positions[code]['shares'])
                                proceeds = shares_to_sell * current_price * (1 - transaction_cost)
                                capital += proceeds
                                positions[code]['shares'] -= shares_to_sell
                                if positions[code]['shares'] == 0:
                                    del positions[code]
                                trades.append({
                                    'date': date,
                                    'code': code,
                                    'action': 'sell',
                                    'price': current_price,
                                    'shares': shares_to_sell,
                                    'value': proceeds
                                })
                else:
                    # 新建仓位
                    if target_per_stock <= capital:
                        shares_to_buy = int(target_per_stock / current_price / (1 + transaction_cost))
                        if shares_to_buy > 0:
                            cost = shares_to_buy * current_price * (1 + transaction_cost)
                            capital -= cost
                            positions[code] = {
                                'shares': shares_to_buy,
                                'cost': current_price
                            }
                            trades.append({
                                'date': date,
                                'code': code,
                                'action': 'buy',
                                'price': current_price,
                                'shares': shares_to_buy,
                                'value': cost
                            })

        # 计算最终市值
        if trade_dates:
            final_prices = data[data['date'] == trade_dates[-1]].set_index('code')['close'].to_dict()
            final_position_value = sum(
                positions[code]['shares'] * final_prices.get(code, positions[code]['cost'])
                for code in positions
            )
            final_total_value = capital + final_position_value
        else:
            final_total_value = initial_capital

        # 计算绩效指标
        portfolio_df = pd.DataFrame(portfolio_values)
        if len(portfolio_df) > 1:
            portfolio_df['returns'] = portfolio_df['total_value'].pct_change()

            total_return = (final_total_value - initial_capital) / initial_capital
            annual_return = (1 + total_return) ** (252 / len(trade_dates)) - 1 if len(trade_dates) > 0 else 0
            volatility = portfolio_df['returns'].std() * np.sqrt(252)
            sharpe_ratio = annual_return / volatility if volatility > 0 else 0

            cummax = portfolio_df['total_value'].cummax()
            drawdown = (portfolio_df['total_value'] - cummax) / cummax
            max_drawdown = drawdown.min()
        else:
            total_return = annual_return = volatility = sharpe_ratio = max_drawdown = 0

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
    print(f"Alpha101多因子策略模块 - {Alpha101Strategy().name}")
    print("WorldQuant 101个经典量化因子的组合应用")
