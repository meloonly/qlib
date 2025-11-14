#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票/ETF 快速分析工具

功能：输入股票代码，快速生成技术分析和风险分析报告

使用方法：
    python quick_analysis.py SH600000 SH600036 SH510300
    python quick_analysis.py --codes SH600000,SH600036,SH510300
    python quick_analysis.py --file stock_list.txt
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("📊 股票/ETF 快速分析工具")
print("=" * 80)
print()


class QuickAnalyzer:
    """股票快速分析器"""

    def __init__(self):
        self.results = {}

    def fetch_stock_data(self, stock_code, days=252):
        """
        获取股票数据（模拟）
        实际使用时应该从 Yahoo Finance、Tushare 等数据源获取

        Args:
            stock_code: 股票代码 (如 SH600000)
            days: 历史天数

        Returns:
            DataFrame: 股票历史数据
        """
        print(f"  正在获取 {stock_code} 的数据...")

        # 生成模拟数据（实际应该调用 yahooquery 或其他数据接口）
        dates = pd.date_range(end=datetime.now(), periods=days, freq='B')

        # 模拟价格走势
        np.random.seed(hash(stock_code) % 1000)
        returns = np.random.randn(days) * 0.02  # 日收益率标准差 2%

        # 添加趋势
        trend = np.linspace(0, 0.3, days)  # 整体上涨趋势
        returns = returns + trend / days

        # 计算价格
        price = 10 * (1 + returns).cumprod()

        # 生成成交量
        volume = np.random.randint(1000000, 10000000, size=days)

        df = pd.DataFrame({
            'date': dates,
            'open': price * (1 + np.random.randn(days) * 0.005),
            'high': price * (1 + np.abs(np.random.randn(days) * 0.01)),
            'low': price * (1 - np.abs(np.random.randn(days) * 0.01)),
            'close': price,
            'volume': volume,
        })

        return df

    def calculate_technical_indicators(self, df):
        """计算技术指标"""

        close = df['close'].values

        # 移动平均线
        ma5 = pd.Series(close).rolling(5).mean().iloc[-1]
        ma10 = pd.Series(close).rolling(10).mean().iloc[-1]
        ma20 = pd.Series(close).rolling(20).mean().iloc[-1]
        ma60 = pd.Series(close).rolling(60).mean().iloc[-1]

        # 相对强弱指标 RSI
        delta = pd.Series(close).diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = rsi.iloc[-1]

        # 布林带
        ma20_series = pd.Series(close).rolling(20).mean()
        std20 = pd.Series(close).rolling(20).std()
        upper_band = (ma20_series + 2 * std20).iloc[-1]
        lower_band = (ma20_series - 2 * std20).iloc[-1]

        # MACD
        ema12 = pd.Series(close).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(close).ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_value = macd.iloc[-1]
        signal_value = signal.iloc[-1]

        return {
            'ma5': ma5,
            'ma10': ma10,
            'ma20': ma20,
            'ma60': ma60,
            'rsi': rsi_value,
            'bollinger_upper': upper_band,
            'bollinger_lower': lower_band,
            'macd': macd_value,
            'macd_signal': signal_value,
        }

    def calculate_risk_metrics(self, df):
        """计算风险指标"""

        returns = df['close'].pct_change().dropna()

        # 收益率统计
        total_return = (df['close'].iloc[-1] / df['close'].iloc[0]) - 1
        annual_return = (1 + total_return) ** (252 / len(df)) - 1

        # 波动率
        volatility = returns.std() * np.sqrt(252)

        # 夏普比率（假设无风险利率3%）
        sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0

        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # VaR (95%)
        var_95 = returns.quantile(0.05)

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe': sharpe,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'daily_return_mean': returns.mean(),
            'daily_return_std': returns.std(),
        }

    def analyze_stock(self, stock_code):
        """分析单只股票"""

        print(f"\n{'='*80}")
        print(f"📈 分析 {stock_code}")
        print('='*80)

        # 获取数据
        df = self.fetch_stock_data(stock_code)

        # 基本信息
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        price_change = (current_price - prev_price) / prev_price

        print(f"\n【基本信息】")
        print(f"  当前价格: ¥{current_price:.2f}")
        print(f"  涨跌幅: {price_change:+.2%}")
        print(f"  最高价: ¥{df['high'].iloc[-1]:.2f}")
        print(f"  最低价: ¥{df['low'].iloc[-1]:.2f}")
        print(f"  成交量: {df['volume'].iloc[-1]:,.0f}")

        # 技术指标
        tech = self.calculate_technical_indicators(df)

        print(f"\n【技术指标】")
        print(f"  MA5:  ¥{tech['ma5']:.2f}")
        print(f"  MA10: ¥{tech['ma10']:.2f}")
        print(f"  MA20: ¥{tech['ma20']:.2f}")
        print(f"  MA60: ¥{tech['ma60']:.2f}")
        print(f"  RSI:  {tech['rsi']:.1f} {'(超买)' if tech['rsi'] > 70 else '(超卖)' if tech['rsi'] < 30 else '(中性)'}")
        print(f"  MACD: {tech['macd']:.3f} {'(金叉)' if tech['macd'] > tech['macd_signal'] else '(死叉)'}")
        print(f"  布林带: ¥{tech['bollinger_lower']:.2f} ~ ¥{tech['bollinger_upper']:.2f}")

        # 风险指标
        risk = self.calculate_risk_metrics(df)

        print(f"\n【风险指标】")
        print(f"  总收益率: {risk['total_return']:+.2%}")
        print(f"  年化收益: {risk['annual_return']:+.2%}")
        print(f"  年化波动: {risk['volatility']:.2%}")
        print(f"  夏普比率: {risk['sharpe']:.2f}")
        print(f"  最大回撤: {risk['max_drawdown']:.2%}")
        print(f"  VaR(95%): {risk['var_95']:.2%}")

        # 交易建议
        print(f"\n【交易建议】")

        # 基于多个指标综合判断
        signals = []

        # 均线判断
        if current_price > tech['ma20']:
            signals.append("价格在MA20上方 (看涨)")
        else:
            signals.append("价格在MA20下方 (看跌)")

        # RSI判断
        if tech['rsi'] > 70:
            signals.append("RSI超买 (警惕回调)")
        elif tech['rsi'] < 30:
            signals.append("RSI超卖 (可能反弹)")
        else:
            signals.append("RSI处于中性区间")

        # MACD判断
        if tech['macd'] > tech['macd_signal']:
            signals.append("MACD金叉 (买入信号)")
        else:
            signals.append("MACD死叉 (卖出信号)")

        # 布林带判断
        if current_price > tech['bollinger_upper']:
            signals.append("突破布林上轨 (超买)")
        elif current_price < tech['bollinger_lower']:
            signals.append("跌破布林下轨 (超卖)")

        for signal in signals:
            print(f"  • {signal}")

        # 综合评分 (0-100)
        score = 50  # 基础分

        # 根据各指标调整分数
        if current_price > tech['ma20']:
            score += 10
        if tech['rsi'] > 50:
            score += 5
        if tech['macd'] > tech['macd_signal']:
            score += 10
        if risk['sharpe'] > 1:
            score += 10
        if risk['max_drawdown'] > -0.2:
            score += 5

        score = min(100, max(0, score))

        print(f"\n  综合评分: {score}/100 ", end="")
        if score >= 70:
            print("⭐⭐⭐ (强烈推荐)")
            recommendation = "强烈推荐"
        elif score >= 60:
            print("⭐⭐ (推荐)")
            recommendation = "推荐"
        elif score >= 50:
            print("⭐ (中性)")
            recommendation = "中性"
        else:
            print("(不推荐)")
            recommendation = "不推荐"

        # 保存结果
        self.results[stock_code] = {
            'current_price': current_price,
            'price_change': price_change,
            'technical': tech,
            'risk': risk,
            'score': score,
            'recommendation': recommendation,
        }

        return self.results[stock_code]

    def compare_stocks(self):
        """对比多只股票"""

        if len(self.results) < 2:
            return

        print(f"\n{'='*80}")
        print(f"📊 股票对比分析")
        print('='*80)

        # 创建对比表
        comparison = []
        for code, data in self.results.items():
            comparison.append({
                '股票代码': code,
                '当前价格': f"¥{data['current_price']:.2f}",
                '涨跌幅': f"{data['price_change']:+.2%}",
                '年化收益': f"{data['risk']['annual_return']:+.2%}",
                '夏普比率': f"{data['risk']['sharpe']:.2f}",
                '最大回撤': f"{data['risk']['max_drawdown']:.2%}",
                'RSI': f"{data['technical']['rsi']:.1f}",
                '综合评分': f"{data['score']}/100",
                '建议': data['recommendation'],
            })

        df_comparison = pd.DataFrame(comparison)
        print("\n" + df_comparison.to_string(index=False))

        # 推荐排序
        print(f"\n【推荐排序】")
        sorted_stocks = sorted(self.results.items(), key=lambda x: x[1]['score'], reverse=True)

        for i, (code, data) in enumerate(sorted_stocks, 1):
            stars = "⭐" * min(3, data['score'] // 25)
            print(f"  {i}. {code}: {data['score']}/100 {stars} - {data['recommendation']}")

    def generate_report(self, output_file='quick_analysis_report.html'):
        """生成HTML报告"""

        from report_generator import ReportGenerator

        print(f"\n{'='*80}")
        print(f"📄 生成分析报告")
        print('='*80)

        # 简化的报告生成
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>股票快速分析报告 - {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; border-left: 4px solid #3498db; padding-left: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        .good {{ color: #27ae60; font-weight: bold; }}
        .bad {{ color: #e74c3c; font-weight: bold; }}
        .neutral {{ color: #7f8c8d; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 股票快速分析报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>分析股票数量: {len(self.results)}</p>

        <h2>分析结果</h2>
        <table>
            <tr>
                <th>股票代码</th>
                <th>当前价格</th>
                <th>涨跌幅</th>
                <th>年化收益</th>
                <th>夏普比率</th>
                <th>RSI</th>
                <th>综合评分</th>
                <th>建议</th>
            </tr>
"""

        sorted_stocks = sorted(self.results.items(), key=lambda x: x[1]['score'], reverse=True)

        for code, data in sorted_stocks:
            price_class = 'good' if data['price_change'] > 0 else 'bad'
            html += f"""
            <tr>
                <td><strong>{code}</strong></td>
                <td>¥{data['current_price']:.2f}</td>
                <td class="{price_class}">{data['price_change']:+.2%}</td>
                <td>{data['risk']['annual_return']:+.2%}</td>
                <td>{data['risk']['sharpe']:.2f}</td>
                <td>{data['technical']['rsi']:.1f}</td>
                <td><strong>{data['score']}/100</strong></td>
                <td>{data['recommendation']}</td>
            </tr>
"""

        html += """
        </table>
    </div>
</body>
</html>
"""

        output_path = Path('reports') / output_file
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\n✓ 报告已生成: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description='股票/ETF 快速分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析多只股票
  python quick_analysis.py SH600000 SH600036 SH510300

  # 使用逗号分隔的代码列表
  python quick_analysis.py --codes SH600000,SH600036,SH510300

  # 从文件读取股票列表
  python quick_analysis.py --file stocks.txt

  # 生成HTML报告
  python quick_analysis.py SH600000 SH600036 --report
        """
    )

    parser.add_argument('stocks', nargs='*', help='股票代码列表')
    parser.add_argument('--codes', help='逗号分隔的股票代码')
    parser.add_argument('--file', help='包含股票代码的文本文件（每行一个代码）')
    parser.add_argument('--report', action='store_true', help='生成HTML报告')

    args = parser.parse_args()

    # 收集股票代码
    stock_codes = []

    if args.stocks:
        stock_codes.extend(args.stocks)

    if args.codes:
        stock_codes.extend(args.codes.split(','))

    if args.file:
        with open(args.file, 'r') as f:
            stock_codes.extend([line.strip() for line in f if line.strip()])

    # 去重
    stock_codes = list(set(stock_codes))

    if not stock_codes:
        print("❌ 错误：请提供至少一个股票代码")
        print("\n使用示例:")
        print("  python quick_analysis.py SH600000 SH600036")
        print("  python quick_analysis.py --codes SH600000,SH600036")
        sys.exit(1)

    print(f"准备分析 {len(stock_codes)} 只股票: {', '.join(stock_codes)}")

    # 创建分析器
    analyzer = QuickAnalyzer()

    # 分析每只股票
    for code in stock_codes:
        try:
            analyzer.analyze_stock(code)
        except Exception as e:
            print(f"\n❌ 分析 {code} 失败: {str(e)}")

    # 对比分析
    if len(analyzer.results) > 1:
        analyzer.compare_stocks()

    # 生成报告
    if args.report:
        analyzer.generate_report()

    print(f"\n{'='*80}")
    print("✅ 分析完成！")
    print('='*80)


if __name__ == '__main__':
    main()
