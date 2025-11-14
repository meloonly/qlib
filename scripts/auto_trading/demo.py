#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化交易系统演示脚本（使用模拟数据）

功能：生成模拟数据并运行完整流程，展示报告生成功能
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("A股/港股/ETF 自动化交易系统 - 演示模式")
print("=" * 70)
print()

# ========== 1. 生成模拟数据 ==========
print("【步骤 1/5】 生成模拟数据")
print("-" * 70)

# 生成50只模拟股票
stocks = [f"SH{600000 + i:06d}" for i in range(50)]
print(f"✓ 生成 {len(stocks)} 只模拟股票")

# 生成模拟信号（随机分数）
np.random.seed(42)
signals = pd.Series(
    np.random.randn(len(stocks)),
    index=stocks,
    name='signal'
)
print(f"✓ 生成 {len(signals)} 个交易信号")
print()

# ========== 2. 生成再平衡计划 ==========
print("【步骤 2/5】 生成组合优化方案")
print("-" * 70)

# 选择Top30股票
top_stocks = signals.nlargest(30)
target_weights = pd.Series(1/30, index=top_stocks.index)

# 生成模拟订单
orders_data = []
for i, stock in enumerate(top_stocks.index[:10]):  # 只显示前10个订单
    delta_w = np.random.uniform(0.01, 0.05)
    orders_data.append({
        'stock': stock,
        'direction': 'BUY' if delta_w > 0 else 'SELL',
        'current_weight': 0.0,
        'target_weight': 1/30,
        'delta_weight': delta_w,
        'amount_value': delta_w * 100000000,  # 1亿资金
    })

orders_df = pd.DataFrame(orders_data)
print(f"✓ 生成 {len(orders_df)} 个交易订单")
print()

# ========== 3. 模拟回测结果 ==========
print("【步骤 3/5】 生成回测结果")
print("-" * 70)

backtest_results = {
    'total_return': 0.15,
    'annual_return': 0.18,
    'bench_total_return': 0.10,
    'bench_annual_return': 0.12,
    'excess_return': 0.05,
    'volatility': 0.20,
    'sharpe_ratio': 1.5,
    'max_drawdown': -0.12,
    'information_ratio': 1.2,
    'tracking_error': 0.08,
    'win_rate': 0.55,
    'turnover': 0.25,
    'total_cost': 500000,
}
print(f"✓ 年化收益: {backtest_results['annual_return']:.2%}")
print(f"✓ 夏普比率: {backtest_results['sharpe_ratio']:.2f}")
print(f"✓ 最大回撤: {backtest_results['max_drawdown']:.2%}")
print()

# ========== 4. 风险分析 ==========
print("【步骤 4/5】 生成风险分析")
print("-" * 70)

risk_analysis = {
    'tracking_error': 0.08,
    'max_position': 0.05,
    'concentration': 0.05,
    'effective_n_stocks': 25,
    'n_positions': 30,
    'risk_decomp': {'factor': 0.6, 'specific': 0.4},
}
print(f"✓ 跟踪误差: {risk_analysis['tracking_error']:.2%}")
print(f"✓ 持仓数量: {risk_analysis['n_positions']}")
print()

# ========== 5. 生成报告 ==========
print("【步骤 5/5】 生成交易报告")
print("-" * 70)

from report_generator import ReportGenerator

reporter = ReportGenerator(output_dir='./reports')

rebalance_plan = {
    'target_weights': target_weights,
    'orders': orders_df,
    'turnover': 0.25,
    'n_buy': 8,
    'n_sell': 2,
    'n_hold': 20,
    'risk_analysis': risk_analysis,
}

signal_quality = {
    'ic_mean': 0.05,
    'ic_std': 0.15,
    'ic_ir': 0.33,
    'signal_coverage': 0.80,
}

date = datetime.now().strftime('%Y-%m-%d')

try:
    report_files = reporter.generate_daily_report(
        date=date,
        signals=signals,
        rebalance_plan=rebalance_plan,
        backtest_results=backtest_results,
        risk_analysis=risk_analysis,
        signal_quality=signal_quality
    )

    print(f"✓ 报告已生成")
    print(f"  HTML: {report_files['html_report']}")
    print(f"  Excel: {report_files['excel_report']}")
    print()

    # ========== 完成 ==========
    print("=" * 70)
    print("✅ 演示完成！")
    print("=" * 70)
    print()
    print("📊 执行摘要:")
    print(f"  信号数量: {len(signals)}")
    print(f"  订单数量: {len(orders_df)}")
    print(f"  换手率: {rebalance_plan['turnover']:.2%}")
    print(f"  年化收益: {backtest_results['annual_return']:.2%}")
    print(f"  夏普比率: {backtest_results['sharpe_ratio']:.2f}")
    print()
    print("📁 报告文件:")
    print(f"  {report_files['html_report']}")
    print(f"  {report_files['excel_report']}")
    print()

    # 显示报告内容预览
    print("📄 HTML 报告预览:")
    print("-" * 70)
    with open(report_files['html_report'], 'r', encoding='utf-8') as f:
        content = f.read()
        # 显示部分内容
        lines = content.split('\n')
        print(f"文件大小: {len(content)} 字符")
        print(f"总行数: {len(lines)}")
        print("✓ HTML 报告包含完整的可视化交易建议和风险分析")
    print()

    print("=" * 70)
    print("提示：在浏览器中打开 HTML 文件可查看完整的可视化报告")
    print("=" * 70)

except Exception as e:
    print(f"❌ 报告生成失败: {str(e)}")
    import traceback
    traceback.print_exc()
