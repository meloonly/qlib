#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略参数优化器

对各个策略进行参数网格搜索，找到最优参数组合。
支持多种优化目标：
- 最大化年化收益率
- 最大化夏普比率
- 最小化最大回撤
- 综合评分

使用方法:
    python parameter_optimizer.py --demo
    python parameter_optimizer.py --demo --strategy dual_ma
    python parameter_optimizer.py --demo --target sharpe_ratio
"""

import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
from itertools import product
import warnings
warnings.filterwarnings('ignore')

# 添加路径
sys.path.append(str(Path(__file__).parent))

from strategies.dual_ma_strategy import DualMAStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy
from strategies.alpha101_strategy import Alpha101Strategy


class ParameterOptimizer:
    """策略参数优化器"""

    def __init__(self):
        self.optimization_results = {}
        self.best_params = {}

    def generate_demo_data(self, n_stocks: int = 30, n_days: int = 400) -> pd.DataFrame:
        """生成演示数据（优化版本，使用向量化操作）"""
        print("📊 生成演示数据...")

        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
        date_strs = dates.strftime('%Y-%m-%d').tolist()

        # 预分配数组
        total_rows = n_stocks * n_days
        codes = []
        all_dates = []
        opens = np.zeros(total_rows)
        highs = np.zeros(total_rows)
        lows = np.zeros(total_rows)
        closes = np.zeros(total_rows)
        volumes = np.zeros(total_rows)

        idx = 0
        for i in range(n_stocks):
            code = f"SH{600000 + i:06d}"
            initial_price = np.random.uniform(10, 100)
            trend = np.random.uniform(-0.0005, 0.0010)
            volatility = np.random.uniform(0.01, 0.03)

            # 向量化生成价格序列
            changes = np.random.normal(trend, volatility, n_days - 1)
            prices = np.zeros(n_days)
            prices[0] = initial_price
            for j in range(1, n_days):
                prices[j] = max(prices[j-1] * (1 + changes[j-1]), 1)

            # 向量化生成OHLCV
            daily_vols = volatility * prices
            open_prices = prices + np.random.normal(0, daily_vols * 0.5)
            high_prices = np.maximum(open_prices, prices) + np.abs(np.random.normal(0, daily_vols * 0.3))
            low_prices = np.minimum(open_prices, prices) - np.abs(np.random.normal(0, daily_vols * 0.3))
            stock_volumes = np.random.uniform(1e6, 1e8, n_days)

            # 批量填充
            end_idx = idx + n_days
            codes.extend([code] * n_days)
            all_dates.extend(date_strs)
            opens[idx:end_idx] = np.round(open_prices, 2)
            highs[idx:end_idx] = np.round(high_prices, 2)
            lows[idx:end_idx] = np.round(low_prices, 2)
            closes[idx:end_idx] = np.round(prices, 2)
            volumes[idx:end_idx] = stock_volumes.astype(int)
            idx = end_idx

        df = pd.DataFrame({
            'code': codes,
            'date': all_dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes.astype(int)
        })
        print(f"✅ 生成了 {n_stocks} 只股票，{n_days} 天的数据")
        return df

    def optimize_dual_ma(self, data: pd.DataFrame, start_date: str, end_date: str,
                        initial_capital: float = 1000000, topk: int = 20) -> pd.DataFrame:
        """
        优化双均线策略参数

        搜索参数:
        - short_window: [3, 5, 10, 15]
        - long_window: [10, 20, 30, 60]
        """
        print("\n🔍 优化双均线策略参数...")

        short_windows = [3, 5, 10, 15]
        long_windows = [10, 20, 30, 60]

        results = []
        total_combinations = sum(1 for s in short_windows for l in long_windows if s < l)
        current = 0

        for short_window in short_windows:
            for long_window in long_windows:
                if short_window >= long_window:
                    continue

                current += 1
                print(f"  测试 ({current}/{total_combinations}): MA{short_window}/{long_window}", end="")

                try:
                    strategy = DualMAStrategy(short_window=short_window, long_window=long_window)
                    result = strategy.backtest(
                        data=data,
                        start_date=start_date,
                        end_date=end_date,
                        initial_capital=initial_capital,
                        topk=topk
                    )

                    results.append({
                        'strategy': 'DualMA',
                        'short_window': short_window,
                        'long_window': long_window,
                        'total_return': result['total_return'],
                        'annual_return': result['annual_return'],
                        'volatility': result['volatility'],
                        'sharpe_ratio': result['sharpe_ratio'],
                        'max_drawdown': result['max_drawdown'],
                        'total_trades': result['total_trades']
                    })
                    print(f" - 收益: {result['total_return']*100:.2f}%, 夏普: {result['sharpe_ratio']:.3f}")

                except Exception as e:
                    print(f" - 失败: {str(e)[:30]}")

        results_df = pd.DataFrame(results)
        self.optimization_results['dual_ma'] = results_df
        return results_df

    def optimize_momentum(self, data: pd.DataFrame, start_date: str, end_date: str,
                         initial_capital: float = 1000000, topk: int = 20) -> pd.DataFrame:
        """
        优化动量策略参数

        搜索参数:
        - lookback_period: [10, 20, 30, 60]
        - holding_period: [3, 5, 10, 20]
        """
        print("\n🔍 优化动量策略参数...")

        lookback_periods = [10, 20, 30, 60]
        holding_periods = [3, 5, 10, 20]

        results = []
        total_combinations = len(lookback_periods) * len(holding_periods)
        current = 0

        for lookback in lookback_periods:
            for holding in holding_periods:
                current += 1
                print(f"  测试 ({current}/{total_combinations}): Lookback{lookback}/Holding{holding}", end="")

                try:
                    strategy = MomentumStrategy(lookback_period=lookback, holding_period=holding)
                    result = strategy.backtest(
                        data=data,
                        start_date=start_date,
                        end_date=end_date,
                        initial_capital=initial_capital,
                        topk=topk
                    )

                    results.append({
                        'strategy': 'Momentum',
                        'lookback_period': lookback,
                        'holding_period': holding,
                        'total_return': result['total_return'],
                        'annual_return': result['annual_return'],
                        'volatility': result['volatility'],
                        'sharpe_ratio': result['sharpe_ratio'],
                        'max_drawdown': result['max_drawdown'],
                        'total_trades': result['total_trades']
                    })
                    print(f" - 收益: {result['total_return']*100:.2f}%, 夏普: {result['sharpe_ratio']:.3f}")

                except Exception as e:
                    print(f" - 失败: {str(e)[:30]}")

        results_df = pd.DataFrame(results)
        self.optimization_results['momentum'] = results_df
        return results_df

    def optimize_mean_reversion(self, data: pd.DataFrame, start_date: str, end_date: str,
                                initial_capital: float = 1000000, topk: int = 20) -> pd.DataFrame:
        """
        优化均值回归策略参数

        搜索参数:
        - window: [10, 20, 30]
        - std_multiplier: [1.5, 2.0, 2.5]
        - rsi_period: [7, 14, 21]
        """
        print("\n🔍 优化均值回归策略参数...")

        windows = [10, 20, 30]
        std_multipliers = [1.5, 2.0, 2.5]
        rsi_periods = [7, 14, 21]

        results = []
        total_combinations = len(windows) * len(std_multipliers) * len(rsi_periods)
        current = 0

        for window in windows:
            for std_mult in std_multipliers:
                for rsi in rsi_periods:
                    current += 1
                    print(f"  测试 ({current}/{total_combinations}): W{window}/Std{std_mult}/RSI{rsi}", end="")

                    try:
                        strategy = MeanReversionStrategy(
                            window=window,
                            std_multiplier=std_mult,
                            rsi_period=rsi
                        )
                        result = strategy.backtest(
                            data=data,
                            start_date=start_date,
                            end_date=end_date,
                            initial_capital=initial_capital,
                            topk=topk
                        )

                        results.append({
                            'strategy': 'MeanReversion',
                            'window': window,
                            'std_multiplier': std_mult,
                            'rsi_period': rsi,
                            'total_return': result['total_return'],
                            'annual_return': result['annual_return'],
                            'volatility': result['volatility'],
                            'sharpe_ratio': result['sharpe_ratio'],
                            'max_drawdown': result['max_drawdown'],
                            'total_trades': result['total_trades']
                        })
                        print(f" - 收益: {result['total_return']*100:.2f}%, 夏普: {result['sharpe_ratio']:.3f}")

                    except Exception as e:
                        print(f" - 失败: {str(e)[:30]}")

        results_df = pd.DataFrame(results)
        self.optimization_results['mean_reversion'] = results_df
        return results_df

    def optimize_alpha101(self, data: pd.DataFrame, start_date: str, end_date: str,
                         initial_capital: float = 1000000, topk: int = 20) -> pd.DataFrame:
        """
        优化Alpha101策略参数

        搜索参数:
        - rebalance_freq: [3, 5, 10, 20]
        - topk: [10, 20, 30]
        """
        print("\n🔍 优化Alpha101策略参数...")

        rebalance_freqs = [3, 5, 10, 20]
        topk_values = [10, 20, 30]

        results = []
        total_combinations = len(rebalance_freqs) * len(topk_values)
        current = 0

        for rebalance_freq in rebalance_freqs:
            for tk in topk_values:
                current += 1
                print(f"  测试 ({current}/{total_combinations}): Rebalance{rebalance_freq}/TopK{tk}", end="")

                try:
                    strategy = Alpha101Strategy()
                    result = strategy.backtest(
                        data=data,
                        start_date=start_date,
                        end_date=end_date,
                        initial_capital=initial_capital,
                        topk=tk,
                        rebalance_freq=rebalance_freq
                    )

                    results.append({
                        'strategy': 'Alpha101',
                        'rebalance_freq': rebalance_freq,
                        'topk': tk,
                        'total_return': result['total_return'],
                        'annual_return': result['annual_return'],
                        'volatility': result['volatility'],
                        'sharpe_ratio': result['sharpe_ratio'],
                        'max_drawdown': result['max_drawdown'],
                        'total_trades': result['total_trades']
                    })
                    print(f" - 收益: {result['total_return']*100:.2f}%, 夏普: {result['sharpe_ratio']:.3f}")

                except Exception as e:
                    print(f" - 失败: {str(e)[:30]}")

        results_df = pd.DataFrame(results)
        self.optimization_results['alpha101'] = results_df
        return results_df

    def find_best_params(self, target: str = 'sharpe_ratio') -> dict:
        """
        找到每个策略的最优参数

        参数:
            target: 优化目标，可选 'sharpe_ratio', 'annual_return', 'max_drawdown'

        返回:
            最优参数字典
        """
        print(f"\n🏆 根据 {target} 寻找最优参数...")

        best_params = {}

        for strategy_name, results_df in self.optimization_results.items():
            if results_df.empty:
                continue

            if target == 'max_drawdown':
                # 最大回撤越小越好（值越接近0）
                best_idx = results_df[target].idxmax()
            else:
                # 其他指标越大越好
                best_idx = results_df[target].idxmax()

            best_row = results_df.loc[best_idx]
            best_params[strategy_name] = best_row.to_dict()

            print(f"\n  {strategy_name} 最优参数:")
            for key, value in best_row.items():
                if key not in ['strategy', 'total_return', 'annual_return', 'volatility',
                              'sharpe_ratio', 'max_drawdown', 'total_trades']:
                    print(f"    {key}: {value}")

            print(f"    年化收益: {best_row['annual_return']*100:.2f}%")
            print(f"    夏普比率: {best_row['sharpe_ratio']:.3f}")
            print(f"    最大回撤: {best_row['max_drawdown']*100:.2f}%")

        self.best_params = best_params
        return best_params

    def generate_optimization_report(self, output_dir: str = "reports") -> None:
        """
        生成优化报告

        参数:
            output_dir: 输出目录
        """
        print("\n📝 生成优化报告...")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 保存所有优化结果
        for strategy_name, results_df in self.optimization_results.items():
            if results_df.empty:
                continue

            file_path = output_path / f"{strategy_name}_optimization.csv"
            results_df.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f"✅ 保存 {strategy_name} 优化结果: {file_path}")

        # 2. 生成最优参数汇总
        if self.best_params:
            summary_data = []
            for strategy_name, params in self.best_params.items():
                row = {'strategy': strategy_name}
                row.update(params)
                summary_data.append(row)

            summary_df = pd.DataFrame(summary_data)
            summary_file = output_path / "best_parameters_summary.csv"
            summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
            print(f"✅ 保存最优参数汇总: {summary_file}")

        # 3. 生成HTML报告
        self._generate_html_report(output_path)

    def _generate_html_report(self, output_path: Path) -> None:
        """生成HTML格式的优化报告"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>策略参数优化报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #3498db; color: white; }
        tr:nth-child(even) { background: #f2f2f2; }
        tr:hover { background: #e8f4f8; }
        .best { background: #d4edda !important; font-weight: bold; }
        .metric-positive { color: #27ae60; }
        .metric-negative { color: #e74c3c; }
        .summary-box { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .recommendation { background: #3498db; color: white; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 策略参数优化报告</h1>
        <p class="timestamp">生成时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>

        <div class="recommendation">
            <h3>🎯 优化目标</h3>
            <p>通过网格搜索找到每个策略的最优参数组合，以最大化夏普比率为主要目标。</p>
        </div>
"""

        # 添加每个策略的优化结果
        for strategy_name, results_df in self.optimization_results.items():
            if results_df.empty:
                continue

            # 找到最优行
            best_idx = results_df['sharpe_ratio'].idxmax()

            html_content += f"""
        <h2>📈 {strategy_name.replace('_', ' ').title()} 策略优化结果</h2>
        <div class="summary-box">
            <p><strong>测试组合数:</strong> {len(results_df)}</p>
            <p><strong>最优夏普比率:</strong> {results_df.loc[best_idx, 'sharpe_ratio']:.4f}</p>
            <p><strong>最优年化收益:</strong> {results_df.loc[best_idx, 'annual_return']*100:.2f}%</p>
        </div>
        <table>
            <tr>
"""
            # 表头
            for col in results_df.columns:
                if col != 'strategy':
                    html_content += f"<th>{col}</th>"
            html_content += "</tr>"

            # 数据行
            for idx, row in results_df.iterrows():
                row_class = 'best' if idx == best_idx else ''
                html_content += f"<tr class='{row_class}'>"
                for col in results_df.columns:
                    if col == 'strategy':
                        continue
                    value = row[col]
                    if isinstance(value, float):
                        if col in ['total_return', 'annual_return', 'volatility', 'max_drawdown']:
                            formatted = f"{value*100:.2f}%"
                            css_class = 'metric-positive' if value > 0 else 'metric-negative'
                            if col == 'max_drawdown':
                                css_class = 'metric-negative' if value < -0.1 else 'metric-positive'
                            html_content += f"<td class='{css_class}'>{formatted}</td>"
                        else:
                            html_content += f"<td>{value:.4f}</td>"
                    else:
                        html_content += f"<td>{value}</td>"
                html_content += "</tr>"

            html_content += "</table>"

        # 最优参数总结
        if self.best_params:
            html_content += """
        <h2>🏆 最优参数总结</h2>
        <table>
            <tr>
                <th>策略</th>
                <th>最优参数</th>
                <th>年化收益</th>
                <th>夏普比率</th>
                <th>最大回撤</th>
            </tr>
"""
            for strategy_name, params in self.best_params.items():
                param_str = ", ".join([
                    f"{k}={v}" for k, v in params.items()
                    if k not in ['strategy', 'total_return', 'annual_return', 'volatility',
                                'sharpe_ratio', 'max_drawdown', 'total_trades']
                ])
                html_content += f"""
            <tr>
                <td><strong>{strategy_name}</strong></td>
                <td>{param_str}</td>
                <td class="{'metric-positive' if params['annual_return'] > 0 else 'metric-negative'}">{params['annual_return']*100:.2f}%</td>
                <td>{params['sharpe_ratio']:.4f}</td>
                <td>{params['max_drawdown']*100:.2f}%</td>
            </tr>
"""
            html_content += "</table>"

        # 使用建议
        html_content += """
        <h2>💡 使用建议</h2>
        <div class="summary-box">
            <ol>
                <li><strong>避免过拟合:</strong> 最优参数是基于历史数据得出的，可能存在过拟合风险。建议使用样本外数据进行验证。</li>
                <li><strong>参数稳定性:</strong> 选择在多个参数组合中都表现良好的策略，而不是只关注单一最优解。</li>
                <li><strong>市场适应性:</strong> 不同市场环境可能需要不同的参数，建议定期重新优化。</li>
                <li><strong>风险控制:</strong> 关注最大回撤指标，确保风险在可接受范围内。</li>
                <li><strong>组合使用:</strong> 考虑将多个策略的最优参数组合使用，以分散风险。</li>
            </ol>
        </div>

        <h2>⚠️ 风险提示</h2>
        <div class="summary-box" style="background: #ffeaa7;">
            <p>1. <strong>历史表现不代表未来:</strong> 过去的最优参数不一定在未来继续有效。</p>
            <p>2. <strong>过拟合风险:</strong> 参数优化可能导致过度拟合历史数据。</p>
            <p>3. <strong>市场变化:</strong> 市场结构变化可能使最优参数失效。</p>
            <p>4. <strong>交易成本:</strong> 实际交易中的滑点和冲击成本可能影响实际表现。</p>
        </div>
    </div>
</body>
</html>
"""

        html_file = output_path / "parameter_optimization_report.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ 生成HTML报告: {html_file}")

    def print_optimization_summary(self) -> None:
        """打印优化总结"""
        print("\n" + "=" * 80)
        print("📊 参数优化总结")
        print("=" * 80)

        for strategy_name, results_df in self.optimization_results.items():
            if results_df.empty:
                continue

            print(f"\n【{strategy_name.upper()}】")
            print(f"  测试参数组合数: {len(results_df)}")

            # 最优（按夏普比率）
            best_sharpe_idx = results_df['sharpe_ratio'].idxmax()
            best_sharpe = results_df.loc[best_sharpe_idx]
            print(f"  最优夏普比率: {best_sharpe['sharpe_ratio']:.4f}")
            print(f"    对应年化收益: {best_sharpe['annual_return']*100:.2f}%")
            print(f"    对应最大回撤: {best_sharpe['max_drawdown']*100:.2f}%")

            # 最优（按收益）
            best_return_idx = results_df['annual_return'].idxmax()
            if best_return_idx != best_sharpe_idx:
                best_return = results_df.loc[best_return_idx]
                print(f"  最高年化收益: {best_return['annual_return']*100:.2f}%")
                print(f"    对应夏普比率: {best_return['sharpe_ratio']:.4f}")

            # 参数范围分析
            print(f"  夏普比率范围: [{results_df['sharpe_ratio'].min():.4f}, {results_df['sharpe_ratio'].max():.4f}]")
            print(f"  年化收益范围: [{results_df['annual_return'].min()*100:.2f}%, {results_df['annual_return'].max()*100:.2f}%]")

        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description='策略参数优化器')
    parser.add_argument('--demo', action='store_true', help='使用演示数据')
    parser.add_argument('--strategy', type=str, default='all',
                       choices=['all', 'dual_ma', 'momentum', 'mean_reversion', 'alpha101'],
                       help='优化哪个策略')
    parser.add_argument('--target', type=str, default='sharpe_ratio',
                       choices=['sharpe_ratio', 'annual_return', 'max_drawdown'],
                       help='优化目标')
    parser.add_argument('--initial-capital', type=float, default=1000000,
                       help='初始资金')
    parser.add_argument('--topk', type=int, default=20, help='选股数量')
    parser.add_argument('--output-dir', type=str, default='reports', help='输出目录')

    args = parser.parse_args()

    # 创建优化器
    optimizer = ParameterOptimizer()

    # 生成数据
    if args.demo:
        print("🎯 使用演示数据模式")
        data = optimizer.generate_demo_data(n_stocks=30, n_days=400)

        dates = sorted(data['date'].unique())
        start_date = dates[200]  # 留出足够历史数据
        end_date = dates[-1]

        print(f"回测区间: {start_date} 至 {end_date}")
        print(f"初始资金: ¥{args.initial_capital:,.0f}")
        print(f"选股数量: Top {args.topk}")
    else:
        print("❌ 暂不支持真实数据，请使用 --demo 参数")
        return

    # 执行优化
    strategies_to_optimize = []
    if args.strategy == 'all':
        strategies_to_optimize = ['dual_ma', 'momentum', 'mean_reversion', 'alpha101']
    else:
        strategies_to_optimize = [args.strategy]

    print(f"\n🚀 开始参数优化...")
    print(f"优化策略: {', '.join(strategies_to_optimize)}")
    print(f"优化目标: {args.target}")

    # 运行优化
    if 'dual_ma' in strategies_to_optimize:
        optimizer.optimize_dual_ma(data, start_date, end_date, args.initial_capital, args.topk)

    if 'momentum' in strategies_to_optimize:
        optimizer.optimize_momentum(data, start_date, end_date, args.initial_capital, args.topk)

    if 'mean_reversion' in strategies_to_optimize:
        optimizer.optimize_mean_reversion(data, start_date, end_date, args.initial_capital, args.topk)

    if 'alpha101' in strategies_to_optimize:
        optimizer.optimize_alpha101(data, start_date, end_date, args.initial_capital, args.topk)

    # 找到最优参数
    optimizer.find_best_params(target=args.target)

    # 打印总结
    optimizer.print_optimization_summary()

    # 生成报告
    optimizer.generate_optimization_report(output_dir=args.output_dir)

    print("\n🎉 参数优化完成！")


if __name__ == '__main__':
    main()
