#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略对比工具

对比多个策略的回测表现，生成详细的对比报告。
支持的策略：
1. 双均线策略 (Dual Moving Average)
2. 动量策略 (Momentum)
3. 均值回归策略 (Mean Reversion)
4. Alpha101 多因子策略

使用方法:
    python strategy_comparison.py --start-date 2023-01-01 --end-date 2023-12-31
    python strategy_comparison.py --demo  # 使用演示数据
"""

import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加路径
sys.path.append(str(Path(__file__).parent))

from strategies.dual_ma_strategy import DualMAStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy
from strategies.alpha101_strategy import Alpha101Strategy


class StrategyComparison:
    """策略对比工具"""

    def __init__(self):
        self.strategies = {
            'Dual_MA_5_20': DualMAStrategy(short_window=5, long_window=20),
            'Momentum_20d': MomentumStrategy(lookback_period=20),
            'Mean_Reversion_20d': MeanReversionStrategy(window=20),
            'Alpha101': Alpha101Strategy()
        }
        self.results = {}

    def generate_demo_data(self, n_stocks: int = 50, n_days: int = 500) -> pd.DataFrame:
        """
        生成演示数据

        参数:
            n_stocks: 股票数量
            n_days: 天数

        返回:
            DataFrame with demo data
        """
        print("📊 生成演示数据...")

        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
        data = []

        for i in range(n_stocks):
            code = f"SH{600000 + i:06d}"

            # 生成价格走势（随机游走 + 趋势）
            initial_price = np.random.uniform(10, 100)
            trend = np.random.uniform(-0.0005, 0.0010)  # 每日趋势
            volatility = np.random.uniform(0.01, 0.03)  # 波动率

            prices = [initial_price]
            for _ in range(n_days - 1):
                change = np.random.normal(trend, volatility)
                new_price = prices[-1] * (1 + change)
                prices.append(max(new_price, 1))  # 确保价格>0

            prices = np.array(prices)

            # 生成 OHLC
            for j, date in enumerate(dates):
                close = prices[j]
                daily_vol = volatility * close
                open_price = close + np.random.normal(0, daily_vol * 0.5)
                high = max(open_price, close) + abs(np.random.normal(0, daily_vol * 0.3))
                low = min(open_price, close) - abs(np.random.normal(0, daily_vol * 0.3))
                volume = np.random.uniform(1e6, 1e8)

                data.append({
                    'code': code,
                    'date': date.strftime('%Y-%m-%d'),
                    'open': round(open_price, 2),
                    'high': round(high, 2),
                    'low': round(low, 2),
                    'close': round(close, 2),
                    'volume': int(volume)
                })

        df = pd.DataFrame(data)
        print(f"✅ 生成了 {n_stocks} 只股票，{n_days} 天的数据")
        return df

    def run_all_strategies(self, data: pd.DataFrame, start_date: str,
                          end_date: str, initial_capital: float = 1000000,
                          topk: int = 30) -> None:
        """
        运行所有策略

        参数:
            data: 历史数据
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_capital: 初始资金
            topk: 每个策略选择前K个股票
        """
        print(f"\n🚀 开始回测所有策略...")
        print(f"回测区间: {start_date} 至 {end_date}")
        print(f"初始资金: ¥{initial_capital:,.0f}")
        print(f"选股数量: Top {topk}\n")

        for name, strategy in self.strategies.items():
            print(f"正在回测: {name}...")
            try:
                result = strategy.backtest(
                    data=data,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    topk=topk
                )
                self.results[name] = result
                print(f"✅ {name} 回测完成 - 收益率: {result['total_return']*100:.2f}%")
            except Exception as e:
                print(f"❌ {name} 回测失败: {str(e)}")
                self.results[name] = None

        print("\n✅ 所有策略回测完成！\n")

    def generate_comparison_table(self) -> pd.DataFrame:
        """
        生成策略对比表

        返回:
            DataFrame with comparison metrics
        """
        comparison_data = []

        for name, result in self.results.items():
            if result is None:
                continue

            comparison_data.append({
                '策略名称': name,
                '最终市值': f"¥{result['final_value']:,.0f}",
                '总收益率': f"{result['total_return']*100:.2f}%",
                '年化收益率': f"{result['annual_return']*100:.2f}%",
                '年化波动率': f"{result['volatility']*100:.2f}%",
                '夏普比率': f"{result['sharpe_ratio']:.3f}",
                '最大回撤': f"{result['max_drawdown']*100:.2f}%",
                '交易次数': result['total_trades']
            })

        return pd.DataFrame(comparison_data)

    def rank_strategies(self) -> pd.DataFrame:
        """
        对策略进行综合排名

        返回:
            DataFrame with rankings
        """
        ranking_data = []

        for name, result in self.results.items():
            if result is None:
                continue

            # 计算综合得分
            # 30% 收益率 + 30% 夏普比率 + 20% 最大回撤（越小越好） + 20% 波动率（越小越好）
            return_score = result['annual_return'] * 100  # 转换为百分比
            sharpe_score = result['sharpe_ratio'] * 20  # 夏普比率通常在0-3之间
            drawdown_score = (1 + result['max_drawdown']) * 100  # 回撤为负，转换为正分
            volatility_score = (1 - result['volatility']) * 100  # 波动率越低越好

            综合得分 = (
                0.30 * return_score +
                0.30 * sharpe_score +
                0.20 * drawdown_score +
                0.20 * volatility_score
            )

            ranking_data.append({
                '策略名称': name,
                '综合得分': 综合得分,
                '年化收益': result['annual_return'],
                '夏普比率': result['sharpe_ratio'],
                '最大回撤': result['max_drawdown'],
                '波动率': result['volatility']
            })

        ranking_df = pd.DataFrame(ranking_data)
        ranking_df = ranking_df.sort_values('综合得分', ascending=False)
        ranking_df['排名'] = range(1, len(ranking_df) + 1)

        return ranking_df[['排名', '策略名称', '综合得分', '年化收益', '夏普比率', '最大回撤', '波动率']]

    def print_comparison_report(self) -> None:
        """打印对比报告"""
        print("=" * 100)
        print("📊 策略对比报告")
        print("=" * 100)
        print()

        # 1. 基础指标对比
        print("1️⃣ 基础指标对比")
        print("-" * 100)
        comparison_table = self.generate_comparison_table()
        print(comparison_table.to_string(index=False))
        print()

        # 2. 策略排名
        print("2️⃣ 综合排名（考虑收益、风险、稳定性）")
        print("-" * 100)
        ranking_table = self.rank_strategies()
        print(ranking_table.to_string(index=False))
        print()

        # 3. 推荐建议
        print("3️⃣ 投资建议")
        print("-" * 100)

        if not ranking_table.empty:
            best_strategy = ranking_table.iloc[0]
            print(f"🏆 综合表现最佳: {best_strategy['策略名称']}")
            print(f"   - 综合得分: {best_strategy['综合得分']:.2f}")
            print(f"   - 年化收益: {best_strategy['年化收益']*100:.2f}%")
            print(f"   - 夏普比率: {best_strategy['夏普比率']:.3f}")
            print()

            # 找到最高收益的策略
            max_return_strategy = ranking_table.loc[ranking_table['年化收益'].idxmax()]
            if max_return_strategy['策略名称'] != best_strategy['策略名称']:
                print(f"💰 最高收益策略: {max_return_strategy['策略名称']}")
                print(f"   - 年化收益: {max_return_strategy['年化收益']*100:.2f}%")
                print(f"   - 风险提示: 高收益可能伴随高风险")
                print()

            # 找到最稳健的策略（最高夏普比率）
            max_sharpe_strategy = ranking_table.loc[ranking_table['夏普比率'].idxmax()]
            if max_sharpe_strategy['策略名称'] != best_strategy['策略名称']:
                print(f"🛡️ 最稳健策略: {max_sharpe_strategy['策略名称']}")
                print(f"   - 夏普比率: {max_sharpe_strategy['夏普比率']:.3f}")
                print(f"   - 风险调整后收益最优")
                print()

        print("=" * 100)
        print()

    def save_results(self, output_dir: str = "reports") -> None:
        """
        保存结果到文件

        参数:
            output_dir: 输出目录
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 保存对比表
        comparison_table = self.generate_comparison_table()
        comparison_file = output_path / "strategy_comparison.csv"
        comparison_table.to_csv(comparison_file, index=False, encoding='utf-8-sig')
        print(f"✅ 对比表已保存: {comparison_file}")

        # 保存排名表
        ranking_table = self.rank_strategies()
        ranking_file = output_path / "strategy_ranking.csv"
        ranking_table.to_csv(ranking_file, index=False, encoding='utf-8-sig')
        print(f"✅ 排名表已保存: {ranking_file}")

        # 保存详细结果
        for name, result in self.results.items():
            if result is None or result.get('trades') is None:
                continue

            trades_df = result['trades']
            if not trades_df.empty:
                trade_file = output_path / f"{name}_trades.csv"
                trades_df.to_csv(trade_file, index=False, encoding='utf-8-sig')
                print(f"✅ {name} 交易记录已保存: {trade_file}")

        print()

    def plot_performance(self) -> None:
        """绘制策略表现对比图（需要matplotlib）"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib

            # 使用支持中文的字体
            matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
            matplotlib.rcParams['axes.unicode_minus'] = False

            fig, axes = plt.subplots(2, 2, figsize=(15, 10))

            # 1. 净值曲线
            ax1 = axes[0, 0]
            for name, result in self.results.items():
                if result is None:
                    continue
                portfolio_history = result['portfolio_history']
                normalized = portfolio_history['total_value'] / result['initial_capital']
                ax1.plot(portfolio_history['date'], normalized, label=name, linewidth=2)

            ax1.set_title('策略净值曲线对比', fontsize=14, fontweight='bold')
            ax1.set_xlabel('日期')
            ax1.set_ylabel('净值（初始=1.0）')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # 2. 收益率对比
            ax2 = axes[0, 1]
            returns = [result['total_return'] * 100 for result in self.results.values() if result]
            names = [name for name, result in self.results.items() if result]
            colors = ['green' if r > 0 else 'red' for r in returns]
            ax2.barh(names, returns, color=colors, alpha=0.7)
            ax2.set_title('总收益率对比 (%)', fontsize=14, fontweight='bold')
            ax2.set_xlabel('收益率 (%)')
            ax2.grid(True, axis='x', alpha=0.3)

            # 3. 夏普比率对比
            ax3 = axes[1, 0]
            sharpe_ratios = [result['sharpe_ratio'] for result in self.results.values() if result]
            ax3.bar(names, sharpe_ratios, alpha=0.7, color='steelblue')
            ax3.set_title('夏普比率对比', fontsize=14, fontweight='bold')
            ax3.set_ylabel('夏普比率')
            ax3.grid(True, axis='y', alpha=0.3)
            plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

            # 4. 最大回撤对比
            ax4 = axes[1, 1]
            drawdowns = [result['max_drawdown'] * 100 for result in self.results.values() if result]
            ax4.bar(names, drawdowns, alpha=0.7, color='salmon')
            ax4.set_title('最大回撤对比 (%)', fontsize=14, fontweight='bold')
            ax4.set_ylabel('最大回撤 (%)')
            ax4.grid(True, axis='y', alpha=0.3)
            plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

            plt.tight_layout()

            # 保存图表
            output_path = Path("reports")
            output_path.mkdir(parents=True, exist_ok=True)
            plot_file = output_path / "strategy_comparison.png"
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            print(f"✅ 对比图表已保存: {plot_file}")

            # plt.show()  # 在支持的环境中显示

        except ImportError:
            print("⚠️ 未安装 matplotlib，跳过图表生成")
        except Exception as e:
            print(f"⚠️ 图表生成失败: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description='策略对比工具')
    parser.add_argument('--start-date', type=str, help='回测开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='回测结束日期 (YYYY-MM-DD)')
    parser.add_argument('--initial-capital', type=float, default=1000000,
                       help='初始资金（默认100万）')
    parser.add_argument('--topk', type=int, default=30,
                       help='选股数量（默认30）')
    parser.add_argument('--demo', action='store_true',
                       help='使用演示数据')
    parser.add_argument('--output-dir', type=str, default='reports',
                       help='输出目录（默认reports）')

    args = parser.parse_args()

    # 创建对比工具
    comparator = StrategyComparison()

    # 生成或加载数据
    if args.demo:
        print("🎯 使用演示数据模式")
        data = comparator.generate_demo_data(n_stocks=50, n_days=500)

        # 使用数据中的日期范围
        dates = sorted(data['date'].unique())
        start_date = dates[250]  # 留出足够的历史数据
        end_date = dates[-1]
    else:
        print("❌ 暂不支持真实数据，请使用 --demo 参数")
        return

    # 运行回测
    comparator.run_all_strategies(
        data=data,
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.initial_capital,
        topk=args.topk
    )

    # 打印报告
    comparator.print_comparison_report()

    # 保存结果
    comparator.save_results(output_dir=args.output_dir)

    # 绘制图表
    comparator.plot_performance()

    print("🎉 策略对比完成！")


if __name__ == '__main__':
    main()
