#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能分析模块

提供详细的业绩归因和统计分析：
- 夏普比率、索提诺比率
- 最大回撤分析
- 月度/季度/年度统计
- 风险调整收益
- 业绩归因分析

使用方法:
    from performance_analyzer import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()
    metrics = analyzer.calculate_metrics(returns)
    analyzer.generate_report(returns, 'report.html')
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path


class PerformanceAnalyzer:
    """
    性能分析器

    计算各种风险和收益指标
    """

    def __init__(self, risk_free_rate: float = 0.03, trading_days_per_year: int = 252):
        """
        初始化

        参数:
            risk_free_rate: 无风险利率（年化）
            trading_days_per_year: 每年交易日数
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days_per_year

    def calculate_metrics(self, returns: pd.Series) -> Dict:
        """
        计算所有性能指标

        参数:
            returns: 日收益率序列

        返回:
            指标字典
        """
        if len(returns) == 0:
            return {}

        returns = returns.dropna()

        # 基础指标
        total_return = (1 + returns).prod() - 1
        annualized_return = (1 + total_return) ** (self.trading_days / len(returns)) - 1
        volatility = returns.std() * np.sqrt(self.trading_days)

        # 夏普比率
        excess_returns = returns - self.risk_free_rate / self.trading_days
        sharpe_ratio = excess_returns.mean() / returns.std() * np.sqrt(self.trading_days) if returns.std() > 0 else 0

        # 索提诺比率（只考虑下行风险）
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(self.trading_days) if len(downside_returns) > 0 else 0
        sortino_ratio = (annualized_return - self.risk_free_rate) / downside_std if downside_std > 0 else 0

        # 卡尔玛比率
        max_dd = self.calculate_max_drawdown(returns)
        calmar_ratio = annualized_return / abs(max_dd) if max_dd != 0 else 0

        # 信息比率（假设基准为0）
        tracking_error = returns.std() * np.sqrt(self.trading_days)
        information_ratio = annualized_return / tracking_error if tracking_error > 0 else 0

        # 胜率
        win_rate = len(returns[returns > 0]) / len(returns) if len(returns) > 0 else 0

        # 盈亏比
        avg_win = returns[returns > 0].mean() if len(returns[returns > 0]) > 0 else 0
        avg_loss = abs(returns[returns < 0].mean()) if len(returns[returns < 0]) > 0 else 0
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        # VaR和CVaR
        var_95 = np.percentile(returns, 5)
        cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else var_95

        # 偏度和峰度
        skewness = returns.skew()
        kurtosis = returns.kurtosis()

        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'information_ratio': information_ratio,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'var_95': var_95,
            'cvar_95': cvar_95,
            'skewness': skewness,
            'kurtosis': kurtosis,
            'best_day': returns.max(),
            'worst_day': returns.min(),
            'avg_daily_return': returns.mean(),
            'trading_days': len(returns)
        }

    def calculate_max_drawdown(self, returns: pd.Series) -> float:
        """
        计算最大回撤

        参数:
            returns: 日收益率序列

        返回:
            最大回撤（负值）
        """
        cum_returns = (1 + returns).cumprod()
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / running_max
        return drawdown.min()

    def calculate_drawdown_series(self, returns: pd.Series) -> pd.DataFrame:
        """
        计算回撤序列

        参数:
            returns: 日收益率序列

        返回:
            回撤DataFrame
        """
        cum_returns = (1 + returns).cumprod()
        running_max = cum_returns.cummax()
        drawdown = (cum_returns - running_max) / running_max

        df = pd.DataFrame({
            'cumulative_return': cum_returns,
            'running_max': running_max,
            'drawdown': drawdown
        })

        return df

    def calculate_rolling_metrics(self, returns: pd.Series, window: int = 60) -> pd.DataFrame:
        """
        计算滚动指标

        参数:
            returns: 日收益率序列
            window: 滚动窗口

        返回:
            滚动指标DataFrame
        """
        rolling_return = returns.rolling(window).apply(lambda x: (1 + x).prod() - 1)
        rolling_vol = returns.rolling(window).std() * np.sqrt(self.trading_days)
        rolling_sharpe = (rolling_return - self.risk_free_rate * window / self.trading_days) / (
                    returns.rolling(window).std() * np.sqrt(self.trading_days))

        df = pd.DataFrame({
            'rolling_return': rolling_return,
            'rolling_volatility': rolling_vol,
            'rolling_sharpe': rolling_sharpe
        })

        return df

    def calculate_monthly_returns(self, returns: pd.Series) -> pd.DataFrame:
        """
        计算月度收益

        参数:
            returns: 带日期索引的日收益率序列

        返回:
            月度收益DataFrame
        """
        if not isinstance(returns.index, pd.DatetimeIndex):
            # 尝试转换
            try:
                returns.index = pd.to_datetime(returns.index)
            except Exception:
                return pd.DataFrame()

        # 按月分组计算
        monthly = returns.groupby([returns.index.year, returns.index.month]).apply(
            lambda x: (1 + x).prod() - 1
        )
        monthly.index.names = ['year', 'month']

        # 转换为宽格式
        monthly_df = monthly.unstack(level='month')
        monthly_df.columns = ['1月', '2月', '3月', '4月', '5月', '6月',
                              '7月', '8月', '9月', '10月', '11月', '12月'][:len(monthly_df.columns)]

        # 计算年度收益
        yearly = returns.groupby(returns.index.year).apply(lambda x: (1 + x).prod() - 1)
        monthly_df['年收益'] = yearly

        return monthly_df

    def calculate_quarterly_returns(self, returns: pd.Series) -> pd.DataFrame:
        """计算季度收益"""
        if not isinstance(returns.index, pd.DatetimeIndex):
            try:
                returns.index = pd.to_datetime(returns.index)
            except Exception:
                return pd.DataFrame()

        quarterly = returns.groupby([returns.index.year, returns.index.quarter]).apply(
            lambda x: (1 + x).prod() - 1
        )
        quarterly.index.names = ['year', 'quarter']

        quarterly_df = quarterly.unstack(level='quarter')
        quarterly_df.columns = ['Q1', 'Q2', 'Q3', 'Q4'][:len(quarterly_df.columns)]

        return quarterly_df

    def calculate_yearly_returns(self, returns: pd.Series) -> pd.Series:
        """计算年度收益"""
        if not isinstance(returns.index, pd.DatetimeIndex):
            try:
                returns.index = pd.to_datetime(returns.index)
            except Exception:
                return pd.Series()

        yearly = returns.groupby(returns.index.year).apply(lambda x: (1 + x).prod() - 1)
        return yearly

    def analyze_winning_streaks(self, returns: pd.Series) -> Dict:
        """
        分析连胜/连亏

        返回:
            streak统计
        """
        is_win = (returns > 0).astype(int)
        is_loss = (returns < 0).astype(int)

        # 连胜
        win_streaks = []
        current_streak = 0
        for win in is_win:
            if win:
                current_streak += 1
            else:
                if current_streak > 0:
                    win_streaks.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            win_streaks.append(current_streak)

        # 连亏
        loss_streaks = []
        current_streak = 0
        for loss in is_loss:
            if loss:
                current_streak += 1
            else:
                if current_streak > 0:
                    loss_streaks.append(current_streak)
                current_streak = 0
        if current_streak > 0:
            loss_streaks.append(current_streak)

        return {
            'max_winning_streak': max(win_streaks) if win_streaks else 0,
            'max_losing_streak': max(loss_streaks) if loss_streaks else 0,
            'avg_winning_streak': np.mean(win_streaks) if win_streaks else 0,
            'avg_losing_streak': np.mean(loss_streaks) if loss_streaks else 0,
            'total_winning_streaks': len(win_streaks),
            'total_losing_streaks': len(loss_streaks)
        }

    def compare_strategies(self, strategies: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        比较多个策略

        参数:
            strategies: {策略名: 收益率序列} 字典

        返回:
            比较DataFrame
        """
        comparison = []

        for name, returns in strategies.items():
            metrics = self.calculate_metrics(returns)
            metrics['strategy'] = name
            comparison.append(metrics)

        df = pd.DataFrame(comparison)
        df = df.set_index('strategy')

        # 排序（按夏普比率）
        df = df.sort_values('sharpe_ratio', ascending=False)

        return df

    def generate_report(self, returns: pd.Series, output_file: str = None, strategy_name: str = "策略") -> str:
        """
        生成HTML性能报告

        参数:
            returns: 日收益率序列
            output_file: 输出文件路径
            strategy_name: 策略名称

        返回:
            报告文件路径
        """
        if output_file is None:
            output_dir = Path(__file__).parent / "reports"
            output_dir.mkdir(exist_ok=True)
            output_file = str(output_dir / f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

        # 计算指标
        metrics = self.calculate_metrics(returns)
        streaks = self.analyze_winning_streaks(returns)
        drawdown_series = self.calculate_drawdown_series(returns)

        # 生成HTML
        html_content = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{strategy_name} - 性能分析报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f7fa;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header .subtitle {{
            opacity: 0.9;
            margin-top: 10px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}
        .card-title {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        .card-value {{
            font-size: 28px;
            font-weight: 700;
        }}
        .positive {{ color: #10b981; }}
        .negative {{ color: #ef4444; }}
        .section {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8fafc;
            font-weight: 600;
        }}
        .metric-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        .metric-label {{
            color: #666;
        }}
        .metric-value {{
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            color: #999;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {strategy_name} - 性能分析报告</h1>
            <div class="subtitle">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-title">📈 总收益率</div>
                <div class="card-value {'positive' if metrics['total_return'] >= 0 else 'negative'}">
                    {metrics['total_return']:.2%}
                </div>
            </div>
            <div class="card">
                <div class="card-title">📊 年化收益率</div>
                <div class="card-value {'positive' if metrics['annualized_return'] >= 0 else 'negative'}">
                    {metrics['annualized_return']:.2%}
                </div>
            </div>
            <div class="card">
                <div class="card-title">⚡ 波动率</div>
                <div class="card-value">{metrics['volatility']:.2%}</div>
            </div>
            <div class="card">
                <div class="card-title">🎯 夏普比率</div>
                <div class="card-value {'positive' if metrics['sharpe_ratio'] >= 1 else ''}">{metrics['sharpe_ratio']:.2f}</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">📐 风险调整收益指标</div>
            <div class="metric-row">
                <span class="metric-label">夏普比率 (Sharpe Ratio)</span>
                <span class="metric-value">{metrics['sharpe_ratio']:.4f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">索提诺比率 (Sortino Ratio)</span>
                <span class="metric-value">{metrics['sortino_ratio']:.4f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">卡尔玛比率 (Calmar Ratio)</span>
                <span class="metric-value">{metrics['calmar_ratio']:.4f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">信息比率 (Information Ratio)</span>
                <span class="metric-value">{metrics['information_ratio']:.4f}</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">⚠️ 风险指标</div>
            <div class="metric-row">
                <span class="metric-label">最大回撤</span>
                <span class="metric-value negative">{metrics['max_drawdown']:.2%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">95% VaR (日)</span>
                <span class="metric-value negative">{metrics['var_95']:.4%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">95% CVaR (日)</span>
                <span class="metric-value negative">{metrics['cvar_95']:.4%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">偏度 (Skewness)</span>
                <span class="metric-value">{metrics['skewness']:.4f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">峰度 (Kurtosis)</span>
                <span class="metric-value">{metrics['kurtosis']:.4f}</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">🎲 交易统计</div>
            <div class="metric-row">
                <span class="metric-label">胜率</span>
                <span class="metric-value">{metrics['win_rate']:.2%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">盈亏比</span>
                <span class="metric-value">{metrics['profit_loss_ratio']:.2f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">最佳单日收益</span>
                <span class="metric-value positive">{metrics['best_day']:.4%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">最差单日收益</span>
                <span class="metric-value negative">{metrics['worst_day']:.4%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">平均日收益</span>
                <span class="metric-value">{metrics['avg_daily_return']:.4%}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">交易天数</span>
                <span class="metric-value">{metrics['trading_days']}</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">🔥 连续表现</div>
            <div class="metric-row">
                <span class="metric-label">最大连胜</span>
                <span class="metric-value positive">{streaks['max_winning_streak']} 天</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">最大连亏</span>
                <span class="metric-value negative">{streaks['max_losing_streak']} 天</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">平均连胜</span>
                <span class="metric-value">{streaks['avg_winning_streak']:.1f} 天</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">平均连亏</span>
                <span class="metric-value">{streaks['avg_losing_streak']:.1f} 天</span>
            </div>
        </div>

        <div class="footer">
            自动化交易系统 - 性能分析报告
        </div>
    </div>
</body>
</html>
        '''

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ 性能报告已生成: {output_file}")
        return output_file


def demo():
    """演示性能分析"""
    print("\n" + "=" * 60)
    print("📊 性能分析模块演示")
    print("=" * 60)

    # 生成模拟收益率数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=500, freq='D')
    returns = pd.Series(
        np.random.normal(0.0005, 0.015, len(dates)),
        index=dates
    )

    # 分析
    analyzer = PerformanceAnalyzer()

    print("\n📈 计算性能指标...")
    metrics = analyzer.calculate_metrics(returns)

    print(f"\n总收益率: {metrics['total_return']:.2%}")
    print(f"年化收益率: {metrics['annualized_return']:.2%}")
    print(f"波动率: {metrics['volatility']:.2%}")
    print(f"夏普比率: {metrics['sharpe_ratio']:.4f}")
    print(f"索提诺比率: {metrics['sortino_ratio']:.4f}")
    print(f"最大回撤: {metrics['max_drawdown']:.2%}")
    print(f"胜率: {metrics['win_rate']:.2%}")
    print(f"盈亏比: {metrics['profit_loss_ratio']:.2f}")

    # 月度收益
    print("\n📅 月度收益统计:")
    monthly = analyzer.calculate_monthly_returns(returns)
    if not monthly.empty:
        print(monthly.round(4))

    # 连续表现
    print("\n🔥 连续表现:")
    streaks = analyzer.analyze_winning_streaks(returns)
    print(f"最大连胜: {streaks['max_winning_streak']} 天")
    print(f"最大连亏: {streaks['max_losing_streak']} 天")

    # 生成报告
    print("\n📄 生成HTML报告...")
    analyzer.generate_report(returns, strategy_name="模拟策略")

    print("\n" + "=" * 60)
    print("✅ 性能分析演示完成")
    print("=" * 60)


if __name__ == '__main__':
    demo()
