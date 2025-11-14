#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
持仓监控和每日交易提示工具

功能：
1. 监控当前持仓的股票表现
2. 生成每日交易建议（买入、卖出、持有）
3. 计算持仓风险和收益
4. 推荐新的投资机会

使用方法：
    # 从CSV文件读取持仓
    python portfolio_monitor.py --portfolio my_portfolio.csv

    # 手动输入持仓
    python portfolio_monitor.py --add SH600000:1000,SH600036:2000

    # 生成每日报告
    python portfolio_monitor.py --portfolio my_portfolio.csv --daily-report
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from quick_analysis import QuickAnalyzer

print("=" * 80)
print("💼 持仓监控和每日交易提示系统")
print("=" * 80)
print()


class PortfolioMonitor:
    """持仓监控器"""

    def __init__(self, portfolio_file=None):
        """
        初始化持仓监控器

        Args:
            portfolio_file: 持仓文件路径 (CSV格式)
                           格式: code,shares,cost_price
                           例如: SH600000,1000,10.5
        """
        self.portfolio = {}
        self.analyzer = QuickAnalyzer()

        if portfolio_file:
            self.load_portfolio(portfolio_file)

    def load_portfolio(self, file_path):
        """从CSV文件加载持仓"""
        print(f"📂 加载持仓文件: {file_path}")

        try:
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                self.portfolio[row['code']] = {
                    'shares': int(row['shares']),
                    'cost_price': float(row['cost_price']),
                }
            print(f"✓ 成功加载 {len(self.portfolio)} 只股票的持仓信息\n")
        except Exception as e:
            print(f"❌ 加载持仓文件失败: {str(e)}\n")

    def add_holding(self, code, shares, cost_price):
        """添加持仓"""
        self.portfolio[code] = {
            'shares': shares,
            'cost_price': cost_price,
        }

    def analyze_portfolio(self):
        """分析整个持仓组合"""

        if not self.portfolio:
            print("❌ 错误：持仓为空，请先添加持仓信息")
            return

        print(f"{'='*80}")
        print(f"💼 持仓分析 - {datetime.now().strftime('%Y-%m-%d')}")
        print('='*80)

        # 分析每只持仓股票
        holdings_analysis = []
        total_cost = 0
        total_market_value = 0

        for code, holding in self.portfolio.items():
            print(f"\n分析 {code}...")

            # 获取当前市场数据
            result = self.analyzer.analyze_stock(code)

            current_price = result['current_price']
            market_value = current_price * holding['shares']
            cost_value = holding['cost_price'] * holding['shares']
            profit = market_value - cost_value
            profit_pct = (profit / cost_value) * 100 if cost_value > 0 else 0

            total_cost += cost_value
            total_market_value += market_value

            holdings_analysis.append({
                'code': code,
                'shares': holding['shares'],
                'cost_price': holding['cost_price'],
                'current_price': current_price,
                'market_value': market_value,
                'cost_value': cost_value,
                'profit': profit,
                'profit_pct': profit_pct,
                'recommendation': result['recommendation'],
                'score': result['score'],
                'rsi': result['technical']['rsi'],
                'sharpe': result['risk']['sharpe'],
            })

        # 汇总持仓报告
        print(f"\n{'='*80}")
        print(f"📊 持仓汇总")
        print('='*80)

        total_profit = total_market_value - total_cost
        total_profit_pct = (total_profit / total_cost) * 100 if total_cost > 0 else 0

        print(f"\n【总体情况】")
        print(f"  持仓股票数: {len(self.portfolio)}")
        print(f"  总成本: ¥{total_cost:,.2f}")
        print(f"  总市值: ¥{total_market_value:,.2f}")
        print(f"  总盈亏: ¥{total_profit:+,.2f} ({total_profit_pct:+.2f}%)")

        # 持仓明细表
        df_holdings = pd.DataFrame(holdings_analysis)

        print(f"\n【持仓明细】")
        print(df_holdings[['code', 'shares', 'cost_price', 'current_price', 'profit_pct', 'recommendation']].to_string(index=False))

        return holdings_analysis

    def generate_daily_signals(self, holdings_analysis):
        """生成每日交易信号"""

        print(f"\n{'='*80}")
        print(f"📈 每日交易建议 - {datetime.now().strftime('%Y-%m-%d')}")
        print('='*80)

        signals = {
            'sell': [],
            'hold': [],
            'buy_more': [],
        }

        for holding in holdings_analysis:
            code = holding['code']
            profit_pct = holding['profit_pct']
            rsi = holding['rsi']
            score = holding['score']

            # 决策逻辑
            if profit_pct > 20 and rsi > 70:
                # 盈利超过20%且RSI超买 → 建议卖出止盈
                signals['sell'].append({
                    'code': code,
                    'reason': f'止盈 (盈利{profit_pct:.1f}%, RSI超买{rsi:.1f})',
                    'priority': 'high',
                })

            elif profit_pct < -10 and score < 50:
                # 亏损超过10%且评分低 → 建议止损
                signals['sell'].append({
                    'code': code,
                    'reason': f'止损 (亏损{profit_pct:.1f}%, 评分{score})',
                    'priority': 'high',
                })

            elif profit_pct < -5 and rsi < 30 and score >= 60:
                # 小幅亏损但RSI超卖且评分高 → 建议加仓
                signals['buy_more'].append({
                    'code': code,
                    'reason': f'加仓机会 (轻微亏损{profit_pct:.1f}%, RSI超卖{rsi:.1f}, 评分{score})',
                    'priority': 'medium',
                })

            elif profit_pct > 0 and score >= 60 and rsi < 70:
                # 盈利中且评分高、未超买 → 建议加仓
                signals['buy_more'].append({
                    'code': code,
                    'reason': f'加仓机会 (盈利{profit_pct:.1f}%, 评分{score})',
                    'priority': 'low',
                })

            else:
                # 其他情况 → 持有观望
                signals['hold'].append({
                    'code': code,
                    'reason': f'持有观望 (盈利{profit_pct:.1f}%, 评分{score})',
                })

        # 输出建议
        if signals['sell']:
            print(f"\n🔴 【建议卖出】 ({len(signals['sell'])}只)")
            for signal in signals['sell']:
                priority_mark = "⚠️⚠️" if signal['priority'] == 'high' else "⚠️"
                print(f"  {priority_mark} {signal['code']}: {signal['reason']}")

        if signals['buy_more']:
            print(f"\n🟢 【建议加仓】 ({len(signals['buy_more'])}只)")
            for signal in signals['buy_more']:
                priority_mark = "⭐⭐" if signal['priority'] == 'medium' else "⭐"
                print(f"  {priority_mark} {signal['code']}: {signal['reason']}")

        if signals['hold']:
            print(f"\n⚪ 【持有观望】 ({len(signals['hold'])}只)")
            for signal in signals['hold']:
                print(f"  • {signal['code']}: {signal['reason']}")

        return signals

    def recommend_new_stocks(self, candidate_codes, max_recommendations=5):
        """推荐新的投资机会"""

        print(f"\n{'='*80}")
        print(f"🌟 新投资机会推荐")
        print('='*80)

        recommendations = []

        print(f"\n分析候选股票池...")
        for code in candidate_codes:
            # 跳过已持有的股票
            if code in self.portfolio:
                continue

            result = self.analyzer.analyze_stock(code)

            # 只推荐高评分的股票
            if result['score'] >= 70:
                recommendations.append({
                    'code': code,
                    'score': result['score'],
                    'current_price': result['current_price'],
                    'annual_return': result['risk']['annual_return'],
                    'sharpe': result['risk']['sharpe'],
                    'rsi': result['technical']['rsi'],
                    'recommendation': result['recommendation'],
                })

        if not recommendations:
            print("\n暂无符合条件的新投资机会")
            return []

        # 按评分排序
        recommendations.sort(key=lambda x: x['score'], reverse=True)

        # 输出推荐
        print(f"\n【推荐股票】 (Top {min(max_recommendations, len(recommendations))})")
        for i, rec in enumerate(recommendations[:max_recommendations], 1):
            stars = "⭐" * min(3, rec['score'] // 25)
            print(f"\n  {i}. {rec['code']} {stars}")
            print(f"     综合评分: {rec['score']}/100")
            print(f"     当前价格: ¥{rec['current_price']:.2f}")
            print(f"     年化收益: {rec['annual_return']:+.2%}")
            print(f"     夏普比率: {rec['sharpe']:.2f}")
            print(f"     建议: {rec['recommendation']}")

        return recommendations[:max_recommendations]

    def generate_daily_report_html(self, holdings_analysis, signals, output_file='daily_portfolio_report.html'):
        """生成每日持仓报告HTML"""

        # 计算总体数据
        total_cost = sum(h['cost_value'] for h in holdings_analysis)
        total_market_value = sum(h['market_value'] for h in holdings_analysis)
        total_profit = total_market_value - total_cost
        total_profit_pct = (total_profit / total_cost) * 100 if total_cost > 0 else 0

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>持仓监控日报 - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; border-left: 4px solid #3498db; padding-left: 10px; }}
        .summary {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .profit {{ color: #27ae60; font-weight: bold; font-size: 1.5em; }}
        .loss {{ color: #e74c3c; font-weight: bold; font-size: 1.5em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        .sell {{ background-color: #ffe6e6; }}
        .buy {{ background-color: #e6ffe6; }}
        .signal-box {{ padding: 15px; margin: 10px 0; border-radius: 6px; }}
        .signal-sell {{ background: #ffebee; border-left: 4px solid #e74c3c; }}
        .signal-buy {{ background: #e8f5e9; border-left: 4px solid #27ae60; }}
        .signal-hold {{ background: #f5f5f5; border-left: 4px solid #7f8c8d; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>💼 持仓监控日报</h1>
        <p>报告日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="summary">
            <h3>总体情况</h3>
            <p>持仓股票数: {len(holdings_analysis)}</p>
            <p>总成本: ¥{total_cost:,.2f}</p>
            <p>总市值: ¥{total_market_value:,.2f}</p>
            <p>总盈亏: <span class="{'profit' if total_profit >= 0 else 'loss'}">¥{total_profit:+,.2f} ({total_profit_pct:+.2f}%)</span></p>
        </div>

        <h2>持仓明细</h2>
        <table>
            <tr>
                <th>股票代码</th>
                <th>持仓数量</th>
                <th>成本价</th>
                <th>现价</th>
                <th>市值</th>
                <th>盈亏</th>
                <th>盈亏率</th>
                <th>评分</th>
                <th>建议</th>
            </tr>
"""

        for holding in holdings_analysis:
            profit_class = 'profit' if holding['profit'] >= 0 else 'loss'
            html += f"""
            <tr>
                <td><strong>{holding['code']}</strong></td>
                <td>{holding['shares']:,}</td>
                <td>¥{holding['cost_price']:.2f}</td>
                <td>¥{holding['current_price']:.2f}</td>
                <td>¥{holding['market_value']:,.2f}</td>
                <td class="{profit_class}">¥{holding['profit']:+,.2f}</td>
                <td class="{profit_class}">{holding['profit_pct']:+.2f}%</td>
                <td>{holding['score']}/100</td>
                <td>{holding['recommendation']}</td>
            </tr>
"""

        html += """
        </table>

        <h2>交易建议</h2>
"""

        # 卖出建议
        if signals['sell']:
            html += """
        <div class="signal-box signal-sell">
            <h3>🔴 建议卖出</h3>
            <ul>
"""
            for signal in signals['sell']:
                html += f"<li><strong>{signal['code']}</strong>: {signal['reason']}</li>\n"
            html += """
            </ul>
        </div>
"""

        # 加仓建议
        if signals['buy_more']:
            html += """
        <div class="signal-box signal-buy">
            <h3>🟢 建议加仓</h3>
            <ul>
"""
            for signal in signals['buy_more']:
                html += f"<li><strong>{signal['code']}</strong>: {signal['reason']}</li>\n"
            html += """
            </ul>
        </div>
"""

        # 持有建议
        if signals['hold']:
            html += """
        <div class="signal-box signal-hold">
            <h3>⚪ 持有观望</h3>
            <ul>
"""
            for signal in signals['hold']:
                html += f"<li><strong>{signal['code']}</strong>: {signal['reason']}</li>\n"
            html += """
            </ul>
        </div>
"""

        html += """
    </div>
</body>
</html>
"""

        output_path = Path('reports') / output_file
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\n✓ 每日报告已生成: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description='持仓监控和每日交易提示工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从CSV文件加载持仓
  python portfolio_monitor.py --portfolio my_portfolio.csv

  # 手动添加持仓
  python portfolio_monitor.py --add SH600000:1000:10.5,SH600036:2000:12.3

  # 生成每日报告
  python portfolio_monitor.py --portfolio my_portfolio.csv --daily-report

  # 推荐新股票
  python portfolio_monitor.py --portfolio my_portfolio.csv --recommend SH600519,SH601318

CSV文件格式 (my_portfolio.csv):
    code,shares,cost_price
    SH600000,1000,10.5
    SH600036,2000,12.3
    SH510300,5000,3.8
        """
    )

    parser.add_argument('--portfolio', help='持仓文件 (CSV格式)')
    parser.add_argument('--add', help='手动添加持仓 (格式: code:shares:cost_price,...)')
    parser.add_argument('--daily-report', action='store_true', help='生成每日HTML报告')
    parser.add_argument('--recommend', help='推荐新股票 (提供候选股票代码，逗号分隔)')

    args = parser.parse_args()

    # 创建监控器
    monitor = PortfolioMonitor(portfolio_file=args.portfolio)

    # 手动添加持仓
    if args.add:
        for item in args.add.split(','):
            code, shares, cost_price = item.split(':')
            monitor.add_holding(code, int(shares), float(cost_price))
            print(f"✓ 添加持仓: {code} {shares}股 @¥{cost_price}")

    # 分析持仓
    holdings_analysis = monitor.analyze_portfolio()

    if holdings_analysis:
        # 生成交易信号
        signals = monitor.generate_daily_signals(holdings_analysis)

        # 推荐新股票
        if args.recommend:
            candidate_codes = args.recommend.split(',')
            monitor.recommend_new_stocks(candidate_codes)

        # 生成每日报告
        if args.daily_report:
            monitor.generate_daily_report_html(holdings_analysis, signals)

    print(f"\n{'='*80}")
    print("✅ 持仓监控完成！")
    print('='*80)


if __name__ == '__main__':
    main()
