#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略组合优化器

实现多策略组合和权重优化：
- 动态权重调整（基于历史表现）
- 自适应学习权重
- 集成学习融合
- 策略表现跟踪

使用方法:
    from strategy_ensemble import StrategyEnsemble

    ensemble = StrategyEnsemble()
    ensemble.add_strategy('dual_ma', strategy_func, weight=0.3)
    signals = ensemble.generate_combined_signals(data)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional, Tuple
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from logger import SystemLogger


class StrategyEnsemble:
    """
    策略集成优化器

    管理多个策略并动态调整权重
    """

    def __init__(self, performance_file: str = None):
        """
        初始化

        参数:
            performance_file: 策略表现记录文件
        """
        self.config = ConfigManager()
        self.logger = SystemLogger('ensemble')

        # 策略注册表
        self.strategies: Dict[str, dict] = {}

        # 性能跟踪文件
        if performance_file is None:
            performance_file = str(Path(__file__).parent / 'strategy_performance.json')
        self.performance_file = performance_file

        # 加载历史表现
        self.performance_history = self._load_performance()

        # 权重优化参数
        self.learning_rate = 0.1  # 权重调整速度
        self.min_weight = 0.05  # 最小权重
        self.max_weight = 0.6  # 最大权重
        self.decay_factor = 0.95  # 历史表现衰减因子

    def _load_performance(self) -> dict:
        """加载历史表现数据"""
        if Path(self.performance_file).exists():
            with open(self.performance_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'strategies': {}, 'daily_records': []}

    def _save_performance(self):
        """保存表现数据"""
        with open(self.performance_file, 'w', encoding='utf-8') as f:
            json.dump(self.performance_history, f, ensure_ascii=False, indent=2, default=str)

    def add_strategy(self, name: str, strategy_func: Callable, weight: float = None,
                     description: str = ''):
        """
        添加策略到集成中

        参数:
            name: 策略名称
            strategy_func: 策略函数，接收data返回signals DataFrame
            weight: 初始权重（None则自动分配）
            description: 策略描述
        """
        if weight is None:
            # 平均分配权重
            n_strategies = len(self.strategies) + 1
            weight = 1.0 / n_strategies

            # 重新分配现有策略权重
            if self.strategies:
                for s_name in self.strategies:
                    self.strategies[s_name]['weight'] = 1.0 / n_strategies

        self.strategies[name] = {
            'func': strategy_func,
            'weight': weight,
            'description': description,
            'total_signals': 0,
            'correct_signals': 0,
            'accuracy': 0.5,  # 初始准确率
            'recent_performance': []  # 最近表现
        }

        # 初始化历史表现
        if name not in self.performance_history['strategies']:
            self.performance_history['strategies'][name] = {
                'cumulative_accuracy': 0.5,
                'total_predictions': 0,
                'correct_predictions': 0,
                'weight_history': [weight],
                'created_at': datetime.now().strftime('%Y-%m-%d')
            }

        self.logger.info(f"添加策略: {name}, 权重: {weight:.4f}")

    def remove_strategy(self, name: str):
        """移除策略"""
        if name in self.strategies:
            del self.strategies[name]
            self._normalize_weights()
            self.logger.info(f"移除策略: {name}")

    def _normalize_weights(self):
        """归一化权重，确保总和为1"""
        if not self.strategies:
            return

        total_weight = sum(s['weight'] for s in self.strategies.values())
        if total_weight > 0:
            for name in self.strategies:
                self.strategies[name]['weight'] /= total_weight

    def get_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return {name: s['weight'] for name, s in self.strategies.items()}

    def set_weights(self, weights: Dict[str, float]):
        """
        手动设置权重

        参数:
            weights: {策略名: 权重} 字典
        """
        for name, weight in weights.items():
            if name in self.strategies:
                self.strategies[name]['weight'] = weight

        self._normalize_weights()

    def generate_combined_signals(self, data: pd.DataFrame,
                                   method: str = 'weighted_vote') -> pd.DataFrame:
        """
        生成综合信号

        参数:
            data: 市场数据
            method: 融合方法
                - 'weighted_vote': 加权投票
                - 'weighted_score': 加权评分
                - 'majority_vote': 多数投票
                - 'unanimous': 全票通过

        返回:
            综合信号DataFrame
        """
        if not self.strategies:
            raise ValueError("没有可用策略，请先添加策略")

        # 收集所有策略信号
        all_signals = {}

        for name, strategy in self.strategies.items():
            try:
                signals = strategy['func'](data)
                if signals is not None and len(signals) > 0:
                    all_signals[name] = signals
                    self.logger.debug(f"{name} 生成 {len(signals)} 条信号")
            except Exception as e:
                self.logger.warning(f"策略 {name} 执行失败: {e}")

        if not all_signals:
            return pd.DataFrame()

        # 根据方法融合信号
        if method == 'weighted_vote':
            combined = self._weighted_vote(all_signals, data)
        elif method == 'weighted_score':
            combined = self._weighted_score(all_signals, data)
        elif method == 'majority_vote':
            combined = self._majority_vote(all_signals, data)
        elif method == 'unanimous':
            combined = self._unanimous_vote(all_signals, data)
        else:
            raise ValueError(f"未知融合方法: {method}")

        return combined

    def _weighted_vote(self, all_signals: Dict[str, pd.DataFrame],
                       data: pd.DataFrame) -> pd.DataFrame:
        """
        加权投票融合

        每个策略的信号按权重累加
        """
        # 获取所有股票代码
        if 'code' in data.columns:
            stocks = data['code'].unique()
        else:
            stocks = data.columns.tolist()
            if 'date' in stocks:
                stocks.remove('date')

        results = []

        for stock in stocks:
            buy_score = 0.0
            sell_score = 0.0
            contributing_strategies = []

            for strategy_name, signals in all_signals.items():
                weight = self.strategies[strategy_name]['weight']

                # 查找该股票的信号
                if 'code' in signals.columns:
                    stock_signal = signals[signals['code'] == stock]
                    if len(stock_signal) > 0:
                        # 检查买入/卖出信号
                        if 'buy_signal' in stock_signal.columns:
                            if stock_signal['buy_signal'].iloc[-1] == 1:
                                buy_score += weight
                                contributing_strategies.append(strategy_name)
                        if 'sell_signal' in stock_signal.columns:
                            if stock_signal['sell_signal'].iloc[-1] == 1:
                                sell_score += weight
                else:
                    # 假设是简单信号格式
                    if stock in signals.index or stock in signals.columns:
                        buy_score += weight * 0.5  # 简单处理

            # 生成综合信号
            if buy_score > 0 or sell_score > 0:
                results.append({
                    'code': stock,
                    'buy_score': buy_score,
                    'sell_score': sell_score,
                    'signal': 'buy' if buy_score > sell_score else 'sell',
                    'confidence': max(buy_score, sell_score),
                    'strategies': len(contributing_strategies),
                    'strategy_names': ','.join(contributing_strategies)
                })

        return pd.DataFrame(results)

    def _weighted_score(self, all_signals: Dict[str, pd.DataFrame],
                        data: pd.DataFrame) -> pd.DataFrame:
        """
        加权评分融合

        综合考虑信号强度和权重
        """
        # 类似weighted_vote但考虑信号强度
        if 'code' in data.columns:
            stocks = data['code'].unique()
        else:
            stocks = [c for c in data.columns if c != 'date']

        results = []

        for stock in stocks:
            total_score = 0.0
            total_weight = 0.0

            for strategy_name, signals in all_signals.items():
                weight = self.strategies[strategy_name]['weight']

                if 'code' in signals.columns:
                    stock_signal = signals[signals['code'] == stock]
                    if len(stock_signal) > 0 and 'signal_strength' in stock_signal.columns:
                        strength = stock_signal['signal_strength'].iloc[-1]
                        total_score += weight * strength
                        total_weight += weight

            if total_weight > 0:
                avg_score = total_score / total_weight
                results.append({
                    'code': stock,
                    'ensemble_score': avg_score,
                    'signal': 'buy' if avg_score > 0.5 else 'sell' if avg_score < -0.5 else 'hold',
                    'confidence': abs(avg_score)
                })

        return pd.DataFrame(results)

    def _majority_vote(self, all_signals: Dict[str, pd.DataFrame],
                       data: pd.DataFrame) -> pd.DataFrame:
        """多数投票（忽略权重）"""
        if 'code' in data.columns:
            stocks = data['code'].unique()
        else:
            stocks = [c for c in data.columns if c != 'date']

        results = []

        for stock in stocks:
            buy_votes = 0
            sell_votes = 0

            for strategy_name, signals in all_signals.items():
                if 'code' in signals.columns:
                    stock_signal = signals[signals['code'] == stock]
                    if len(stock_signal) > 0:
                        if 'buy_signal' in stock_signal.columns and stock_signal['buy_signal'].iloc[-1] == 1:
                            buy_votes += 1
                        if 'sell_signal' in stock_signal.columns and stock_signal['sell_signal'].iloc[-1] == 1:
                            sell_votes += 1

            total_strategies = len(all_signals)
            if buy_votes > total_strategies / 2 or sell_votes > total_strategies / 2:
                results.append({
                    'code': stock,
                    'buy_votes': buy_votes,
                    'sell_votes': sell_votes,
                    'signal': 'buy' if buy_votes > sell_votes else 'sell',
                    'vote_ratio': max(buy_votes, sell_votes) / total_strategies
                })

        return pd.DataFrame(results)

    def _unanimous_vote(self, all_signals: Dict[str, pd.DataFrame],
                        data: pd.DataFrame) -> pd.DataFrame:
        """全票通过（所有策略一致）"""
        if 'code' in data.columns:
            stocks = data['code'].unique()
        else:
            stocks = [c for c in data.columns if c != 'date']

        results = []

        for stock in stocks:
            buy_votes = 0
            sell_votes = 0
            total = len(all_signals)

            for strategy_name, signals in all_signals.items():
                if 'code' in signals.columns:
                    stock_signal = signals[signals['code'] == stock]
                    if len(stock_signal) > 0:
                        if 'buy_signal' in stock_signal.columns and stock_signal['buy_signal'].iloc[-1] == 1:
                            buy_votes += 1
                        if 'sell_signal' in stock_signal.columns and stock_signal['sell_signal'].iloc[-1] == 1:
                            sell_votes += 1

            # 全票通过
            if buy_votes == total:
                results.append({'code': stock, 'signal': 'buy', 'unanimous': True})
            elif sell_votes == total:
                results.append({'code': stock, 'signal': 'sell', 'unanimous': True})

        return pd.DataFrame(results)

    def update_performance(self, strategy_name: str, prediction: str,
                           actual_result: str, date: str = None):
        """
        更新策略表现

        参数:
            strategy_name: 策略名称
            prediction: 预测信号 ('buy' or 'sell')
            actual_result: 实际结果 ('up' or 'down')
            date: 日期
        """
        if strategy_name not in self.strategies:
            return

        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # 判断预测是否正确
        correct = (prediction == 'buy' and actual_result == 'up') or \
                  (prediction == 'sell' and actual_result == 'down')

        # 更新本地统计
        self.strategies[strategy_name]['total_signals'] += 1
        if correct:
            self.strategies[strategy_name]['correct_signals'] += 1

        # 计算准确率
        total = self.strategies[strategy_name]['total_signals']
        correct_count = self.strategies[strategy_name]['correct_signals']
        accuracy = correct_count / total if total > 0 else 0.5

        self.strategies[strategy_name]['accuracy'] = accuracy

        # 更新最近表现（滑动窗口）
        self.strategies[strategy_name]['recent_performance'].append(1 if correct else 0)
        if len(self.strategies[strategy_name]['recent_performance']) > 30:
            self.strategies[strategy_name]['recent_performance'].pop(0)

        # 更新历史记录
        hist = self.performance_history['strategies'][strategy_name]
        hist['total_predictions'] += 1
        if correct:
            hist['correct_predictions'] += 1
        hist['cumulative_accuracy'] = hist['correct_predictions'] / hist['total_predictions']

        # 记录每日表现
        daily_record = {
            'date': date,
            'strategy': strategy_name,
            'prediction': prediction,
            'actual': actual_result,
            'correct': correct
        }
        self.performance_history['daily_records'].append(daily_record)

        # 保留最近90天记录
        if len(self.performance_history['daily_records']) > 90 * len(self.strategies):
            self.performance_history['daily_records'] = \
                self.performance_history['daily_records'][-90 * len(self.strategies):]

        self._save_performance()
        self.logger.debug(f"更新 {strategy_name} 表现: {'正确' if correct else '错误'}, 准确率: {accuracy:.2%}")

    def adjust_weights_by_performance(self, method: str = 'accuracy'):
        """
        根据历史表现调整权重

        参数:
            method: 调整方法
                - 'accuracy': 基于累积准确率
                - 'recent': 基于近期表现
                - 'sharpe': 基于夏普比率（需要收益数据）
                - 'exponential': 指数加权近期表现
        """
        if len(self.strategies) < 2:
            return

        if method == 'accuracy':
            # 基于累积准确率
            scores = {}
            for name, strategy in self.strategies.items():
                scores[name] = strategy['accuracy']

        elif method == 'recent':
            # 基于最近30天表现
            scores = {}
            for name, strategy in self.strategies.items():
                recent = strategy['recent_performance']
                if recent:
                    scores[name] = sum(recent) / len(recent)
                else:
                    scores[name] = 0.5

        elif method == 'exponential':
            # 指数加权近期表现（近期权重更大）
            scores = {}
            for name, strategy in self.strategies.items():
                recent = strategy['recent_performance']
                if recent:
                    weights = [self.decay_factor ** i for i in range(len(recent) - 1, -1, -1)]
                    weighted_sum = sum(r * w for r, w in zip(recent, weights))
                    scores[name] = weighted_sum / sum(weights)
                else:
                    scores[name] = 0.5

        else:
            self.logger.warning(f"未知权重调整方法: {method}")
            return

        # 计算新权重
        total_score = sum(scores.values())
        if total_score == 0:
            return

        new_weights = {}
        for name, score in scores.items():
            # 应用学习率平滑调整
            old_weight = self.strategies[name]['weight']
            target_weight = score / total_score
            new_weight = old_weight + self.learning_rate * (target_weight - old_weight)

            # 限制权重范围
            new_weight = max(self.min_weight, min(self.max_weight, new_weight))
            new_weights[name] = new_weight

        # 归一化
        total_new = sum(new_weights.values())
        for name in new_weights:
            self.strategies[name]['weight'] = new_weights[name] / total_new
            # 记录权重历史
            self.performance_history['strategies'][name]['weight_history'].append(
                self.strategies[name]['weight']
            )

        self._save_performance()
        self.logger.info(f"权重已调整: {self.get_weights()}")

    def optimize_weights_grid_search(self, data: pd.DataFrame, validation_data: pd.DataFrame,
                                      grid_size: int = 10) -> Dict[str, float]:
        """
        网格搜索最优权重组合

        参数:
            data: 训练数据
            validation_data: 验证数据
            grid_size: 网格精度

        返回:
            最优权重
        """
        if len(self.strategies) < 2:
            return self.get_weights()

        strategy_names = list(self.strategies.keys())
        n_strategies = len(strategy_names)

        best_weights = None
        best_score = -float('inf')

        # 简化：对于2-3个策略使用网格搜索
        if n_strategies == 2:
            for w1 in np.linspace(0.1, 0.9, grid_size):
                w2 = 1.0 - w1
                weights = {strategy_names[0]: w1, strategy_names[1]: w2}
                score = self._evaluate_weights(weights, data, validation_data)
                if score > best_score:
                    best_score = score
                    best_weights = weights

        elif n_strategies == 3:
            for w1 in np.linspace(0.1, 0.8, grid_size // 2):
                for w2 in np.linspace(0.1, 0.8 - w1, grid_size // 2):
                    w3 = 1.0 - w1 - w2
                    if w3 >= 0.1:
                        weights = {
                            strategy_names[0]: w1,
                            strategy_names[1]: w2,
                            strategy_names[2]: w3
                        }
                        score = self._evaluate_weights(weights, data, validation_data)
                        if score > best_score:
                            best_score = score
                            best_weights = weights

        else:
            # 对于更多策略，使用随机搜索
            best_weights = self._random_search_weights(data, validation_data, n_iterations=100)

        if best_weights:
            self.set_weights(best_weights)
            self.logger.info(f"最优权重: {best_weights}, 得分: {best_score:.4f}")

        return best_weights or self.get_weights()

    def _evaluate_weights(self, weights: Dict[str, float], data: pd.DataFrame,
                          validation_data: pd.DataFrame) -> float:
        """评估权重组合的表现"""
        # 临时设置权重
        old_weights = self.get_weights()
        self.set_weights(weights)

        try:
            # 生成训练集信号
            signals = self.generate_combined_signals(data)
            if len(signals) == 0:
                return 0.0

            # 在验证集上评估
            # 简化评估：计算信号准确率
            correct = 0
            total = 0

            for _, signal in signals.iterrows():
                code = signal['code']
                predicted_signal = signal.get('signal', 'hold')

                # 检查验证数据中的实际表现
                if 'code' in validation_data.columns:
                    val_data = validation_data[validation_data['code'] == code]
                    if len(val_data) > 1:
                        price_change = val_data['close'].iloc[-1] / val_data['close'].iloc[0] - 1
                        actual = 'up' if price_change > 0 else 'down'

                        if (predicted_signal == 'buy' and actual == 'up') or \
                                (predicted_signal == 'sell' and actual == 'down'):
                            correct += 1
                        total += 1

            accuracy = correct / total if total > 0 else 0.5
            return accuracy

        finally:
            # 恢复原权重
            self.set_weights(old_weights)

    def _random_search_weights(self, data: pd.DataFrame, validation_data: pd.DataFrame,
                                n_iterations: int = 100) -> Dict[str, float]:
        """随机搜索最优权重"""
        strategy_names = list(self.strategies.keys())
        best_weights = None
        best_score = -float('inf')

        for _ in range(n_iterations):
            # 生成随机权重
            random_weights = np.random.dirichlet(np.ones(len(strategy_names)))
            weights = dict(zip(strategy_names, random_weights))

            score = self._evaluate_weights(weights, data, validation_data)
            if score > best_score:
                best_score = score
                best_weights = weights

        return best_weights

    def get_performance_summary(self) -> pd.DataFrame:
        """获取所有策略表现摘要"""
        summary = []
        for name, strategy in self.strategies.items():
            hist = self.performance_history['strategies'].get(name, {})

            recent_perf = strategy['recent_performance']
            recent_accuracy = sum(recent_perf) / len(recent_perf) if recent_perf else 0

            summary.append({
                '策略名称': name,
                '当前权重': f"{strategy['weight']:.2%}",
                '累积准确率': f"{strategy['accuracy']:.2%}",
                '近期准确率': f"{recent_accuracy:.2%}",
                '总信号数': strategy['total_signals'],
                '正确信号': strategy['correct_signals'],
                '创建时间': hist.get('created_at', 'N/A')
            })

        return pd.DataFrame(summary)

    def print_status(self):
        """打印当前状态"""
        print("\n" + "=" * 60)
        print("📊 策略组合状态")
        print("=" * 60)

        if not self.strategies:
            print("暂无策略")
            return

        print(f"策略数量: {len(self.strategies)}")
        print(f"融合方法: 加权投票")
        print()

        print("各策略详情:")
        print("-" * 60)

        for name, strategy in self.strategies.items():
            print(f"📌 {name}")
            print(f"   权重: {strategy['weight']:.2%}")
            print(f"   准确率: {strategy['accuracy']:.2%}")
            print(f"   总信号: {strategy['total_signals']}")

            recent = strategy['recent_performance']
            if recent:
                recent_acc = sum(recent) / len(recent)
                print(f"   近期表现: {recent_acc:.2%} (最近{len(recent)}次)")
            print()

        # 显示权重分布
        weights = self.get_weights()
        print("权重分布:")
        for name, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            bar_length = int(weight * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            print(f"  {name:15} {bar} {weight:.1%}")

        print("=" * 60)


def create_demo_strategies():
    """创建演示策略"""

    def dual_ma_strategy(data: pd.DataFrame) -> pd.DataFrame:
        """双均线策略"""
        results = []

        if 'code' in data.columns:
            for code in data['code'].unique():
                stock_data = data[data['code'] == code].copy()
                if len(stock_data) < 20:
                    continue

                stock_data['ma5'] = stock_data['close'].rolling(5).mean()
                stock_data['ma20'] = stock_data['close'].rolling(20).mean()

                latest = stock_data.iloc[-1]
                if latest['ma5'] > latest['ma20']:
                    results.append({
                        'code': code,
                        'buy_signal': 1,
                        'sell_signal': 0,
                        'signal_strength': (latest['ma5'] - latest['ma20']) / latest['ma20']
                    })
                elif latest['ma5'] < latest['ma20']:
                    results.append({
                        'code': code,
                        'buy_signal': 0,
                        'sell_signal': 1,
                        'signal_strength': (latest['ma20'] - latest['ma5']) / latest['ma20']
                    })

        return pd.DataFrame(results)

    def momentum_strategy(data: pd.DataFrame) -> pd.DataFrame:
        """动量策略"""
        results = []

        if 'code' in data.columns:
            for code in data['code'].unique():
                stock_data = data[data['code'] == code].copy()
                if len(stock_data) < 20:
                    continue

                momentum = stock_data['close'].pct_change(20).iloc[-1]

                if momentum > 0.05:
                    results.append({
                        'code': code,
                        'buy_signal': 1,
                        'sell_signal': 0,
                        'signal_strength': min(momentum, 0.3)
                    })
                elif momentum < -0.05:
                    results.append({
                        'code': code,
                        'buy_signal': 0,
                        'sell_signal': 1,
                        'signal_strength': min(abs(momentum), 0.3)
                    })

        return pd.DataFrame(results)

    def rsi_strategy(data: pd.DataFrame) -> pd.DataFrame:
        """RSI策略"""
        results = []

        if 'code' in data.columns:
            for code in data['code'].unique():
                stock_data = data[data['code'] == code].copy()
                if len(stock_data) < 15:
                    continue

                # 计算RSI
                delta = stock_data['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / (loss + 1e-10)
                rsi = 100 - (100 / (1 + rs))

                current_rsi = rsi.iloc[-1]

                if current_rsi < 30:  # 超卖
                    results.append({
                        'code': code,
                        'buy_signal': 1,
                        'sell_signal': 0,
                        'signal_strength': (30 - current_rsi) / 30
                    })
                elif current_rsi > 70:  # 超买
                    results.append({
                        'code': code,
                        'buy_signal': 0,
                        'sell_signal': 1,
                        'signal_strength': (current_rsi - 70) / 30
                    })

        return pd.DataFrame(results)

    return {
        'dual_ma': dual_ma_strategy,
        'momentum': momentum_strategy,
        'rsi': rsi_strategy
    }


def demo():
    """演示策略组合优化器"""
    print("\n" + "=" * 60)
    print("🎯 策略组合优化器演示")
    print("=" * 60)

    # 创建模拟数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

    data_list = []
    for code in ['SH600000', 'SH600036', 'SH601318']:
        initial_price = np.random.uniform(10, 50)
        prices = [initial_price]
        for _ in range(99):
            prices.append(prices[-1] * (1 + np.random.normal(0.001, 0.02)))

        for i, date in enumerate(dates):
            data_list.append({
                'code': code,
                'date': date.strftime('%Y-%m-%d'),
                'close': prices[i]
            })

    data = pd.DataFrame(data_list)

    # 创建集成优化器
    ensemble = StrategyEnsemble()

    # 添加策略
    strategies = create_demo_strategies()
    ensemble.add_strategy('dual_ma', strategies['dual_ma'], weight=0.4, description='双均线策略')
    ensemble.add_strategy('momentum', strategies['momentum'], weight=0.35, description='动量策略')
    ensemble.add_strategy('rsi', strategies['rsi'], weight=0.25, description='RSI超买超卖')

    # 显示状态
    ensemble.print_status()

    # 生成综合信号
    print("\n📡 生成综合信号...")
    signals = ensemble.generate_combined_signals(data, method='weighted_vote')
    print(f"生成 {len(signals)} 个综合信号")

    if len(signals) > 0:
        print("\n前5个信号:")
        print(signals.head().to_string())

    # 模拟更新表现
    print("\n📈 模拟策略表现更新...")
    for _ in range(20):
        for strategy_name in ensemble.strategies.keys():
            # 随机模拟结果
            prediction = np.random.choice(['buy', 'sell'])
            actual = np.random.choice(['up', 'down'])
            ensemble.update_performance(strategy_name, prediction, actual)

    # 根据表现调整权重
    print("\n⚖️ 根据表现调整权重...")
    print(f"调整前: {ensemble.get_weights()}")
    ensemble.adjust_weights_by_performance(method='exponential')
    print(f"调整后: {ensemble.get_weights()}")

    # 显示表现摘要
    print("\n📊 策略表现摘要:")
    summary = ensemble.get_performance_summary()
    print(summary.to_string())

    print("\n" + "=" * 60)
    print("✅ 策略组合优化器演示完成")
    print("=" * 60)


if __name__ == '__main__':
    demo()
