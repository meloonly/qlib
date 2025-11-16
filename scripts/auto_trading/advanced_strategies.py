#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级量化策略

包含：
1. 海龟交易法则 (Turtle Trading)
2. 配对交易策略 (Pair Trading)
3. 机器学习策略 (RandomForest)

使用方法:
    from advanced_strategies import TurtleTrading, PairTrading, MLStrategy
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


class TurtleTrading:
    """
    海龟交易法则

    基于Richard Dennis的经典策略：
    - 使用通道突破进行入场
    - 使用ATR进行头寸管理
    - 严格的止损规则
    """

    def __init__(self, entry_window: int = 20, exit_window: int = 10, atr_period: int = 20):
        """
        初始化参数

        参数:
            entry_window: 入场通道周期（默认20日突破）
            exit_window: 离场通道周期（默认10日突破）
            atr_period: ATR计算周期
        """
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.atr_period = atr_period

    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """计算平均真实波幅(ATR)"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        return atr

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成海龟交易信号

        参数:
            data: DataFrame，需包含 code, date, open, high, low, close, volume

        返回:
            DataFrame with signals
        """
        results = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].copy()
            stock_data = stock_data.sort_values('date')

            if len(stock_data) < self.entry_window + 10:
                continue

            # 计算通道
            stock_data['high_channel'] = stock_data['high'].rolling(self.entry_window).max()
            stock_data['low_channel'] = stock_data['low'].rolling(self.entry_window).min()
            stock_data['exit_high'] = stock_data['high'].rolling(self.exit_window).max()
            stock_data['exit_low'] = stock_data['low'].rolling(self.exit_window).min()

            # 计算ATR
            stock_data['atr'] = self.calculate_atr(
                stock_data['high'],
                stock_data['low'],
                stock_data['close']
            )

            # 生成信号
            stock_data['buy_signal'] = 0
            stock_data['sell_signal'] = 0

            # 突破上轨买入
            stock_data.loc[
                stock_data['high'] > stock_data['high_channel'].shift(1),
                'buy_signal'
            ] = 1

            # 跌破下轨卖出
            stock_data.loc[
                stock_data['low'] < stock_data['exit_low'].shift(1),
                'sell_signal'
            ] = 1

            # 计算信号强度（基于ATR）
            stock_data['signal_strength'] = np.where(
                stock_data['buy_signal'] == 1,
                (stock_data['close'] - stock_data['high_channel'].shift(1)) / stock_data['atr'],
                0
            )

            results.append(stock_data)

        if not results:
            return pd.DataFrame()

        return pd.concat(results, ignore_index=True)

    def calculate_position_size(self, capital: float, risk_per_trade: float, atr: float, price: float) -> int:
        """
        海龟头寸管理

        参数:
            capital: 总资金
            risk_per_trade: 每笔交易风险比例（如0.01表示1%）
            atr: 平均真实波幅
            price: 当前价格

        返回:
            建议买入股数
        """
        if atr == 0 or price == 0:
            return 0

        # 每单位风险金额
        risk_amount = capital * risk_per_trade

        # 基于2倍ATR止损
        stop_distance = 2 * atr

        # 计算股数
        shares = int(risk_amount / stop_distance)

        # 确保不超过资金
        max_shares = int(capital * 0.1 / price)  # 单笔最多10%资金
        shares = min(shares, max_shares)

        # 调整为100的整数倍
        shares = (shares // 100) * 100

        return max(shares, 0)


class PairTrading:
    """
    配对交易策略

    利用两个高度相关股票的价差回归进行交易：
    - 计算协整关系
    - 监控价差偏离
    - 均值回归交易
    """

    def __init__(self, lookback: int = 60, entry_z: float = 2.0, exit_z: float = 0.5):
        """
        初始化参数

        参数:
            lookback: 回顾周期
            entry_z: 入场Z-score阈值
            exit_z: 离场Z-score阈值
        """
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z

    def find_cointegrated_pairs(self, data: pd.DataFrame, threshold: float = 0.05) -> List[Tuple[str, str, float]]:
        """
        寻找协整的股票对

        参数:
            data: 宽格式价格数据（列为股票代码）
            threshold: p-value阈值

        返回:
            协整对列表 [(stock1, stock2, p_value), ...]
        """
        try:
            from statsmodels.tsa.stattools import coint
        except ImportError:
            print("请安装statsmodels: pip install statsmodels")
            return []

        stocks = data.columns.tolist()
        n = len(stocks)
        pairs = []

        for i in range(n):
            for j in range(i + 1, n):
                s1 = data[stocks[i]].dropna()
                s2 = data[stocks[j]].dropna()

                # 确保长度相同
                common_idx = s1.index.intersection(s2.index)
                if len(common_idx) < self.lookback:
                    continue

                s1 = s1.loc[common_idx]
                s2 = s2.loc[common_idx]

                # 协整检验
                try:
                    _, p_value, _ = coint(s1, s2)
                    if p_value < threshold:
                        pairs.append((stocks[i], stocks[j], p_value))
                except Exception:
                    continue

        # 按p-value排序
        pairs.sort(key=lambda x: x[2])
        return pairs

    def calculate_spread(self, price1: pd.Series, price2: pd.Series) -> Tuple[pd.Series, float, float]:
        """
        计算标准化价差

        返回:
            (z_score_series, hedge_ratio, spread_mean)
        """
        # 简单对冲比率（回归系数）
        from numpy.linalg import lstsq

        X = np.column_stack([price2.values, np.ones(len(price2))])
        Y = price1.values
        hedge_ratio = lstsq(X, Y, rcond=None)[0][0]

        # 计算价差
        spread = price1 - hedge_ratio * price2

        # 标准化
        spread_mean = spread.rolling(self.lookback).mean()
        spread_std = spread.rolling(self.lookback).std()
        z_score = (spread - spread_mean) / spread_std

        return z_score, hedge_ratio, spread.mean()

    def generate_signals(self, price1: pd.Series, price2: pd.Series) -> pd.DataFrame:
        """
        生成配对交易信号

        参数:
            price1: 股票1价格序列
            price2: 股票2价格序列

        返回:
            信号DataFrame
        """
        z_score, hedge_ratio, _ = self.calculate_spread(price1, price2)

        signals = pd.DataFrame(index=price1.index)
        signals['z_score'] = z_score
        signals['hedge_ratio'] = hedge_ratio

        # 初始化信号
        signals['position'] = 0

        # 生成信号
        # z_score > entry_z: 做空价差（做空stock1，做多stock2）
        # z_score < -entry_z: 做多价差（做多stock1，做空stock2）
        signals.loc[z_score > self.entry_z, 'position'] = -1  # Short spread
        signals.loc[z_score < -self.entry_z, 'position'] = 1  # Long spread

        # 平仓信号
        signals.loc[abs(z_score) < self.exit_z, 'position'] = 0

        return signals

    def backtest_pair(self, price1: pd.Series, price2: pd.Series,
                      initial_capital: float = 1000000) -> Dict:
        """
        回测配对交易

        返回:
            回测结果字典
        """
        signals = self.generate_signals(price1, price2)
        z_score = signals['z_score']
        hedge_ratio = signals['hedge_ratio'].iloc[-1]

        # 简单回测
        capital = initial_capital
        position = 0
        shares1 = 0
        shares2 = 0
        entry_price1 = 0
        entry_price2 = 0

        returns = []

        for i in range(1, len(signals)):
            if pd.isna(z_score.iloc[i]):
                returns.append(0)
                continue

            current_z = z_score.iloc[i]
            current_price1 = price1.iloc[i]
            current_price2 = price2.iloc[i]

            # 开仓
            if position == 0:
                if current_z > self.entry_z:  # Short spread
                    position = -1
                    shares1 = int(capital * 0.5 / current_price1)
                    shares2 = int(shares1 * hedge_ratio)
                    entry_price1 = current_price1
                    entry_price2 = current_price2
                elif current_z < -self.entry_z:  # Long spread
                    position = 1
                    shares1 = int(capital * 0.5 / current_price1)
                    shares2 = int(shares1 * hedge_ratio)
                    entry_price1 = current_price1
                    entry_price2 = current_price2

            # 平仓
            elif abs(current_z) < self.exit_z:
                if position == 1:  # Long spread
                    pnl = shares1 * (current_price1 - entry_price1) - shares2 * (current_price2 - entry_price2)
                else:  # Short spread
                    pnl = -shares1 * (current_price1 - entry_price1) + shares2 * (current_price2 - entry_price2)

                capital += pnl
                position = 0
                shares1 = 0
                shares2 = 0

            returns.append((capital - initial_capital) / initial_capital)

        final_return = (capital - initial_capital) / initial_capital

        return {
            'total_return': final_return,
            'sharpe_ratio': np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252),
            'max_drawdown': np.min(returns),
            'trades': len([r for r in returns if r != 0]),
            'final_capital': capital
        }


class MLStrategy:
    """
    机器学习策略

    使用随机森林预测股票涨跌：
    - 特征工程：技术指标
    - 模型训练：RandomForest
    - 信号生成：基于预测概率
    """

    def __init__(self, n_estimators: int = 100, lookback: int = 20, threshold: float = 0.6):
        """
        初始化参数

        参数:
            n_estimators: 随机森林树的数量
            lookback: 特征回顾周期
            threshold: 预测概率阈值
        """
        self.n_estimators = n_estimators
        self.lookback = lookback
        self.threshold = threshold
        self.model = None
        self.feature_names = []

    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        创建特征

        参数:
            data: 包含 open, high, low, close, volume 的DataFrame

        返回:
            特征DataFrame
        """
        df = data.copy()

        # 收益率特征
        df['return_1d'] = df['close'].pct_change(1)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_10d'] = df['close'].pct_change(10)
        df['return_20d'] = df['close'].pct_change(20)

        # 波动率特征
        df['volatility_5d'] = df['return_1d'].rolling(5).std()
        df['volatility_10d'] = df['return_1d'].rolling(10).std()
        df['volatility_20d'] = df['return_1d'].rolling(20).std()

        # 动量特征
        df['momentum_5d'] = df['close'] / df['close'].shift(5) - 1
        df['momentum_10d'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_20d'] = df['close'] / df['close'].shift(20) - 1

        # 均线偏离
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma_deviation_5'] = df['close'] / df['ma5'] - 1
        df['ma_deviation_10'] = df['close'] / df['ma10'] - 1
        df['ma_deviation_20'] = df['close'] / df['ma20'] - 1

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        # 成交量特征
        df['volume_change'] = df['volume'].pct_change()
        df['volume_ma5'] = df['volume'].rolling(5).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma5']

        # 价格位置
        df['high_low_range'] = (df['high'] - df['low']) / df['close']
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)

        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # 标签：未来5日涨跌
        df['target'] = (df['close'].shift(-5) > df['close']).astype(int)

        return df

    def train(self, data: pd.DataFrame) -> Dict:
        """
        训练模型

        参数:
            data: 训练数据

        返回:
            训练结果
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, precision_score, recall_score
        except ImportError:
            print("请安装scikit-learn: pip install scikit-learn")
            return {'success': False, 'error': 'scikit-learn not installed'}

        # 创建特征
        df = self.create_features(data)
        df = df.dropna()

        if len(df) < 100:
            return {'success': False, 'error': 'Not enough data'}

        # 选择特征
        self.feature_names = [
            'return_1d', 'return_5d', 'return_10d', 'return_20d',
            'volatility_5d', 'volatility_10d', 'volatility_20d',
            'momentum_5d', 'momentum_10d', 'momentum_20d',
            'ma_deviation_5', 'ma_deviation_10', 'ma_deviation_20',
            'rsi', 'volume_ratio', 'high_low_range', 'close_position',
            'macd_hist'
        ]

        X = df[self.feature_names].values
        y = df['target'].values

        # 分割数据
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # 训练模型
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=10,
            min_samples_split=20,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_train, y_train)

        # 评估
        y_pred = self.model.predict(X_test)

        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)

        # 特征重要性
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_))
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            'success': True,
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'top_features': top_features,
            'train_samples': len(X_train),
            'test_samples': len(X_test)
        }

    def predict(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        预测信号

        参数:
            data: 最新数据

        返回:
            带预测结果的DataFrame
        """
        if self.model is None:
            raise ValueError("模型未训练，请先调用train方法")

        df = self.create_features(data)
        df = df.dropna(subset=self.feature_names)

        if len(df) == 0:
            return pd.DataFrame()

        X = df[self.feature_names].values

        # 预测概率
        probabilities = self.model.predict_proba(X)[:, 1]

        df = df.copy()
        df['prediction_prob'] = probabilities
        df['buy_signal'] = (probabilities > self.threshold).astype(int)
        df['sell_signal'] = (probabilities < (1 - self.threshold)).astype(int)
        df['signal_strength'] = probabilities

        return df

    def generate_portfolio_signals(self, data: pd.DataFrame, topk: int = 10) -> pd.DataFrame:
        """
        为多只股票生成投资组合信号

        参数:
            data: 包含code列的DataFrame
            topk: 选择前k只股票

        返回:
            信号DataFrame
        """
        all_signals = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].copy()
            stock_data = stock_data.sort_values('date')

            if len(stock_data) < 50:
                continue

            try:
                # 训练模型
                train_result = self.train(stock_data)
                if not train_result.get('success'):
                    continue

                # 预测
                predictions = self.predict(stock_data)
                if len(predictions) == 0:
                    continue

                # 获取最新信号
                latest = predictions.iloc[-1]
                all_signals.append({
                    'code': code,
                    'date': latest.get('date', stock_data['date'].iloc[-1]),
                    'prediction_prob': latest['prediction_prob'],
                    'buy_signal': latest['buy_signal'],
                    'accuracy': train_result['accuracy'],
                    'precision': train_result['precision']
                })
            except Exception as e:
                continue

        if not all_signals:
            return pd.DataFrame()

        signals_df = pd.DataFrame(all_signals)
        signals_df = signals_df.sort_values('prediction_prob', ascending=False)

        # 选择top k
        return signals_df.head(topk)


def demo_turtle_trading():
    """演示海龟交易策略"""
    print("\n" + "=" * 60)
    print("🐢 海龟交易法则演示")
    print("=" * 60)

    # 生成模拟数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

    data_list = []
    for code in ['SH600000', 'SH600036']:
        initial_price = np.random.uniform(10, 50)
        prices = [initial_price]
        for _ in range(99):
            change = np.random.normal(0.001, 0.025)
            prices.append(max(prices[-1] * (1 + change), 1))

        for i, date in enumerate(dates):
            price = prices[i]
            data_list.append({
                'code': code,
                'date': date.strftime('%Y-%m-%d'),
                'open': round(price * (1 + np.random.normal(0, 0.005)), 2),
                'high': round(price * (1 + abs(np.random.normal(0, 0.01))), 2),
                'low': round(price * (1 - abs(np.random.normal(0, 0.01))), 2),
                'close': round(price, 2),
                'volume': int(np.random.uniform(1e6, 1e7))
            })

    data = pd.DataFrame(data_list)

    # 运行策略
    turtle = TurtleTrading(entry_window=20, exit_window=10)
    signals = turtle.generate_signals(data)

    print(f"生成 {len(signals)} 条信号记录")

    # 统计信号
    buy_signals = signals[signals['buy_signal'] == 1]
    sell_signals = signals[signals['sell_signal'] == 1]

    print(f"买入信号: {len(buy_signals)} 次")
    print(f"卖出信号: {len(sell_signals)} 次")

    # 头寸计算示例
    if len(signals) > 0:
        latest = signals.iloc[-1]
        position_size = turtle.calculate_position_size(
            capital=1000000,
            risk_per_trade=0.01,
            atr=latest.get('atr', 1.0),
            price=latest['close']
        )
        print(f"建议头寸大小: {position_size} 股")


def demo_ml_strategy():
    """演示机器学习策略"""
    print("\n" + "=" * 60)
    print("🤖 机器学习策略演示")
    print("=" * 60)

    # 生成模拟数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=300, freq='D')

    data_list = []
    for code in ['SH600000']:
        initial_price = 50
        prices = [initial_price]
        volumes = [1e7]

        for _ in range(299):
            # 加入一些趋势
            trend = 0.0003
            change = np.random.normal(trend, 0.02)
            prices.append(max(prices[-1] * (1 + change), 1))
            volumes.append(max(volumes[-1] * (1 + np.random.normal(0, 0.1)), 1e6))

        for i, date in enumerate(dates):
            price = prices[i]
            vol = int(volumes[i])
            data_list.append({
                'code': code,
                'date': date.strftime('%Y-%m-%d'),
                'open': round(price * (1 + np.random.normal(0, 0.005)), 2),
                'high': round(price * (1 + abs(np.random.normal(0, 0.01))), 2),
                'low': round(price * (1 - abs(np.random.normal(0, 0.01))), 2),
                'close': round(price, 2),
                'volume': vol
            })

    data = pd.DataFrame(data_list)

    # 训练模型
    ml_strategy = MLStrategy(n_estimators=50)
    train_result = ml_strategy.train(data)

    if train_result['success']:
        print(f"模型准确率: {train_result['accuracy']:.2%}")
        print(f"模型精确率: {train_result['precision']:.2%}")
        print(f"模型召回率: {train_result['recall']:.2%}")
        print(f"\n重要特征:")
        for feature, importance in train_result['top_features']:
            print(f"  {feature}: {importance:.4f}")

        # 预测
        predictions = ml_strategy.predict(data)
        latest = predictions.iloc[-1]
        print(f"\n最新预测:")
        print(f"  上涨概率: {latest['prediction_prob']:.2%}")
        print(f"  买入信号: {'是' if latest['buy_signal'] else '否'}")
    else:
        print(f"训练失败: {train_result.get('error')}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("📈 高级量化策略演示")
    print("=" * 60)

    # 演示海龟交易
    demo_turtle_trading()

    # 演示机器学习策略
    demo_ml_strategy()

    print("\n" + "=" * 60)
    print("✅ 高级策略演示完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
