#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级风险管理模块

实现组合级风险控制：
- 组合VaR和CVaR监控
- 相关性分析（避免过度集中）
- 动态止损（跟踪止损）
- 杠杆控制和保证金监控
- 风险预算分配

使用方法:
    from risk_manager import RiskManager

    rm = RiskManager()
    rm.set_portfolio(positions, prices)
    risk_report = rm.comprehensive_risk_check()
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from logger import SystemLogger


class RiskManager:
    """
    高级风险管理器

    提供组合级风险监控和控制
    """

    def __init__(self):
        """初始化风险管理器"""
        self.config = ConfigManager()
        self.logger = SystemLogger('risk_manager')

        # 持仓数据
        self.positions = {}  # {code: {'shares': int, 'avg_cost': float, 'current_price': float}}
        self.price_history = {}  # {code: pd.Series}

        # 跟踪止损状态
        self.trailing_stops = {}  # {code: {'high_water_mark': float, 'stop_price': float}}

        # 风险参数
        self.risk_params = self.config.get_risk_params()
        self.var_confidence = 0.95
        self.correlation_threshold = 0.7  # 相关性警告阈值
        self.max_leverage = 1.0  # 最大杠杆倍数
        self.max_concentration = 0.25  # 单一资产最大占比

        # 风险历史记录
        self.risk_history_file = Path(__file__).parent / 'risk_history.json'
        self.risk_history = self._load_risk_history()

    def _load_risk_history(self) -> dict:
        """加载风险历史"""
        if self.risk_history_file.exists():
            with open(self.risk_history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'daily_var': [], 'alerts': [], 'stop_loss_events': []}

    def _save_risk_history(self):
        """保存风险历史"""
        # 保留最近90天记录
        for key in self.risk_history:
            if len(self.risk_history[key]) > 90:
                self.risk_history[key] = self.risk_history[key][-90:]

        with open(self.risk_history_file, 'w', encoding='utf-8') as f:
            json.dump(self.risk_history, f, ensure_ascii=False, indent=2, default=str)

    def set_portfolio(self, positions: Dict[str, dict], price_history: Dict[str, pd.Series] = None):
        """
        设置投资组合数据

        参数:
            positions: {code: {'shares': int, 'avg_cost': float, 'current_price': float}}
            price_history: {code: pd.Series of prices}
        """
        self.positions = positions
        if price_history:
            self.price_history = price_history

        # 初始化跟踪止损
        for code, pos in positions.items():
            if code not in self.trailing_stops:
                self.trailing_stops[code] = {
                    'high_water_mark': pos['current_price'],
                    'stop_price': pos['current_price'] * (1 + self.risk_params.get('stop_loss_threshold', -0.08))
                }

    def calculate_portfolio_value(self) -> float:
        """计算投资组合总市值"""
        total = 0.0
        for code, pos in self.positions.items():
            total += pos['shares'] * pos['current_price']
        return total

    # ==================== VaR监控 ====================

    def calculate_portfolio_var(self, confidence: float = None, horizon: int = 1) -> Dict[str, float]:
        """
        计算组合VaR

        参数:
            confidence: 置信度（如0.95表示95%）
            horizon: 持有期（天数）

        返回:
            VaR和CVaR结果
        """
        if confidence is None:
            confidence = self.var_confidence

        if not self.price_history:
            self.logger.warning("无历史价格数据，无法计算VaR")
            return {'var': 0, 'cvar': 0, 'var_pct': 0, 'cvar_pct': 0}

        # 计算组合收益率
        portfolio_returns = self._calculate_portfolio_returns()

        if len(portfolio_returns) < 30:
            self.logger.warning(f"历史数据不足（{len(portfolio_returns)}天），VaR计算可能不准确")

        # 历史模拟法VaR
        var_percentile = (1 - confidence) * 100
        var_daily = np.percentile(portfolio_returns, var_percentile)

        # 调整持有期
        var_horizon = var_daily * np.sqrt(horizon)

        # 计算CVaR（条件VaR/期望短缺）
        cvar_daily = portfolio_returns[portfolio_returns <= var_daily].mean()
        cvar_horizon = cvar_daily * np.sqrt(horizon)

        # 转换为金额
        portfolio_value = self.calculate_portfolio_value()
        var_amount = abs(var_horizon * portfolio_value)
        cvar_amount = abs(cvar_horizon * portfolio_value)

        result = {
            'var': var_amount,
            'cvar': cvar_amount,
            'var_pct': abs(var_horizon) * 100,
            'cvar_pct': abs(cvar_horizon) * 100,
            'confidence': confidence,
            'horizon': horizon,
            'portfolio_value': portfolio_value
        }

        # 记录历史
        self.risk_history['daily_var'].append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'var_pct': result['var_pct'],
            'cvar_pct': result['cvar_pct'],
            'portfolio_value': portfolio_value
        })

        self._save_risk_history()

        return result

    def _calculate_portfolio_returns(self) -> np.ndarray:
        """计算组合历史收益率"""
        if not self.price_history:
            return np.array([])

        # 获取最短的历史长度
        min_length = min(len(series) for series in self.price_history.values())

        # 计算各资产权重
        portfolio_value = self.calculate_portfolio_value()
        weights = {}
        for code, pos in self.positions.items():
            weights[code] = (pos['shares'] * pos['current_price']) / portfolio_value

        # 计算加权组合收益
        portfolio_returns = np.zeros(min_length - 1)

        for code, weight in weights.items():
            if code in self.price_history:
                prices = self.price_history[code].values[-min_length:]
                returns = np.diff(prices) / prices[:-1]
                portfolio_returns += weight * returns

        return portfolio_returns

    def parametric_var(self, confidence: float = 0.95) -> float:
        """
        参数法VaR（假设正态分布）

        返回:
            VaR百分比
        """
        portfolio_returns = self._calculate_portfolio_returns()
        if len(portfolio_returns) == 0:
            return 0.0

        mean_return = np.mean(portfolio_returns)
        std_return = np.std(portfolio_returns)

        # 正态分布的分位数
        from scipy.stats import norm
        z_score = norm.ppf(1 - confidence)

        var_pct = -(mean_return + z_score * std_return)
        return var_pct * 100

    # ==================== 相关性分析 ====================

    def calculate_correlation_matrix(self) -> pd.DataFrame:
        """
        计算资产相关性矩阵

        返回:
            相关性矩阵DataFrame
        """
        if not self.price_history or len(self.price_history) < 2:
            return pd.DataFrame()

        # 构建收益率DataFrame
        returns_dict = {}
        min_length = min(len(series) for series in self.price_history.values())

        for code, prices in self.price_history.items():
            prices_array = prices.values[-min_length:]
            returns = np.diff(prices_array) / prices_array[:-1]
            returns_dict[code] = returns

        returns_df = pd.DataFrame(returns_dict)

        # 计算相关性矩阵
        correlation_matrix = returns_df.corr()

        return correlation_matrix

    def check_concentration_risk(self) -> Dict[str, any]:
        """
        检查集中度风险

        返回:
            集中度分析结果
        """
        if not self.positions:
            return {'issues': [], 'hhi': 0, 'max_weight': 0}

        portfolio_value = self.calculate_portfolio_value()

        # 计算各资产权重
        weights = {}
        for code, pos in self.positions.items():
            weights[code] = (pos['shares'] * pos['current_price']) / portfolio_value

        # 计算HHI（赫芬达尔指数）
        hhi = sum(w ** 2 for w in weights.values())

        # 检查问题
        issues = []
        warnings = []

        # 单一资产集中度
        max_weight = max(weights.values())
        max_weight_code = max(weights, key=weights.get)

        if max_weight > self.max_concentration:
            issues.append({
                'type': 'over_concentration',
                'code': max_weight_code,
                'weight': max_weight,
                'threshold': self.max_concentration,
                'message': f'{max_weight_code} 占比 {max_weight:.1%} 超过阈值 {self.max_concentration:.1%}'
            })

        # 相关性集中度
        corr_matrix = self.calculate_correlation_matrix()
        if not corr_matrix.empty:
            high_corr_pairs = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i + 1, len(corr_matrix.columns)):
                    corr = corr_matrix.iloc[i, j]
                    if abs(corr) > self.correlation_threshold:
                        code1 = corr_matrix.columns[i]
                        code2 = corr_matrix.columns[j]
                        high_corr_pairs.append((code1, code2, corr))

            if high_corr_pairs:
                for code1, code2, corr in high_corr_pairs:
                    combined_weight = weights.get(code1, 0) + weights.get(code2, 0)
                    warnings.append({
                        'type': 'high_correlation',
                        'codes': [code1, code2],
                        'correlation': corr,
                        'combined_weight': combined_weight,
                        'message': f'{code1} 与 {code2} 相关性 {corr:.2f}，合计占比 {combined_weight:.1%}'
                    })

        # HHI评估
        if hhi > 0.25:  # 高度集中
            issues.append({
                'type': 'portfolio_concentration',
                'hhi': hhi,
                'message': f'组合HHI指数 {hhi:.4f} 过高，建议分散投资'
            })

        return {
            'weights': weights,
            'hhi': hhi,
            'max_weight': max_weight,
            'max_weight_code': max_weight_code,
            'issues': issues,
            'warnings': warnings,
            'correlation_matrix': corr_matrix
        }

    # ==================== 动态止损 ====================

    def update_trailing_stops(self):
        """
        更新跟踪止损价格

        当价格创新高时，上调止损价格
        """
        trailing_pct = abs(self.risk_params.get('stop_loss_threshold', -0.08))

        for code, pos in self.positions.items():
            current_price = pos['current_price']

            if code not in self.trailing_stops:
                self.trailing_stops[code] = {
                    'high_water_mark': current_price,
                    'stop_price': current_price * (1 - trailing_pct)
                }
            else:
                # 更新高水位线
                if current_price > self.trailing_stops[code]['high_water_mark']:
                    self.trailing_stops[code]['high_water_mark'] = current_price
                    # 上调止损价
                    new_stop = current_price * (1 - trailing_pct)
                    self.trailing_stops[code]['stop_price'] = new_stop
                    self.logger.info(f"{code} 创新高 {current_price:.2f}，止损价上调至 {new_stop:.2f}")

    def check_trailing_stop_triggers(self) -> List[Dict]:
        """
        检查是否触发跟踪止损

        返回:
            触发止损的股票列表
        """
        self.update_trailing_stops()

        triggered = []

        for code, pos in self.positions.items():
            current_price = pos['current_price']
            stop_info = self.trailing_stops.get(code, {})
            stop_price = stop_info.get('stop_price', 0)
            high_water_mark = stop_info.get('high_water_mark', current_price)

            if current_price <= stop_price:
                drawdown = (current_price - high_water_mark) / high_water_mark * 100

                trigger_info = {
                    'code': code,
                    'current_price': current_price,
                    'stop_price': stop_price,
                    'high_water_mark': high_water_mark,
                    'drawdown_pct': drawdown,
                    'shares': pos['shares'],
                    'potential_loss': pos['shares'] * (pos['avg_cost'] - current_price),
                    'message': f'{code} 触发跟踪止损，从高点 {high_water_mark:.2f} 回撤 {abs(drawdown):.2f}%'
                }

                triggered.append(trigger_info)

                # 记录止损事件
                self.risk_history['stop_loss_events'].append({
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'code': code,
                    'drawdown_pct': drawdown,
                    'stop_type': 'trailing'
                })

                self.logger.log_risk_alert('trailing_stop', code, drawdown, trigger_info['message'])

        if triggered:
            self._save_risk_history()

        return triggered

    def set_custom_stop(self, code: str, stop_price: float):
        """
        设置自定义止损价

        参数:
            code: 股票代码
            stop_price: 止损价格
        """
        if code in self.positions:
            self.trailing_stops[code] = {
                'high_water_mark': self.positions[code]['current_price'],
                'stop_price': stop_price
            }
            self.logger.info(f"设置 {code} 止损价为 {stop_price:.2f}")

    # ==================== 杠杆控制 ====================

    def calculate_leverage(self, total_equity: float) -> Dict[str, float]:
        """
        计算当前杠杆率

        参数:
            total_equity: 账户净资产

        返回:
            杠杆分析结果
        """
        portfolio_value = self.calculate_portfolio_value()

        # 杠杆 = 总敞口 / 净资产
        leverage = portfolio_value / total_equity if total_equity > 0 else 0

        result = {
            'leverage': leverage,
            'portfolio_value': portfolio_value,
            'total_equity': total_equity,
            'excess_leverage': max(0, leverage - self.max_leverage),
            'is_overleveraged': leverage > self.max_leverage
        }

        if result['is_overleveraged']:
            # 计算需要减仓金额
            target_value = total_equity * self.max_leverage
            result['reduce_amount'] = portfolio_value - target_value
            result['message'] = f'杠杆率 {leverage:.2f}x 超过限制 {self.max_leverage:.2f}x，需减仓 ¥{result["reduce_amount"]:,.2f}'
        else:
            result['message'] = f'杠杆率 {leverage:.2f}x 在控制范围内'

        return result

    def margin_call_check(self, total_equity: float, maintenance_margin: float = 0.25) -> Dict:
        """
        检查保证金追缴风险

        参数:
            total_equity: 净资产
            maintenance_margin: 维持保证金比例

        返回:
            保证金状态
        """
        portfolio_value = self.calculate_portfolio_value()
        margin_ratio = total_equity / portfolio_value if portfolio_value > 0 else 1

        result = {
            'margin_ratio': margin_ratio,
            'maintenance_margin': maintenance_margin,
            'is_safe': margin_ratio > maintenance_margin * 1.2,  # 20%安全边际
            'distance_to_call': margin_ratio - maintenance_margin
        }

        if margin_ratio <= maintenance_margin:
            result['status'] = 'MARGIN_CALL'
            result['message'] = f'触发保证金追缴！当前保证金比例 {margin_ratio:.2%}'
        elif margin_ratio <= maintenance_margin * 1.2:
            result['status'] = 'WARNING'
            result['message'] = f'保证金接近警戒线，当前 {margin_ratio:.2%}'
        else:
            result['status'] = 'SAFE'
            result['message'] = f'保证金充足，当前 {margin_ratio:.2%}'

        return result

    # ==================== 综合风险检查 ====================

    def comprehensive_risk_check(self, total_equity: float = None) -> Dict:
        """
        综合风险检查

        参数:
            total_equity: 账户净资产（用于杠杆计算）

        返回:
            完整的风险报告
        """
        if total_equity is None:
            total_equity = self.calculate_portfolio_value()

        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'portfolio_value': self.calculate_portfolio_value(),
            'total_equity': total_equity,
            'risk_level': 'LOW',  # LOW, MEDIUM, HIGH, CRITICAL
            'issues': [],
            'warnings': [],
            'metrics': {}
        }

        # 1. VaR分析
        if self.price_history:
            var_result = self.calculate_portfolio_var()
            report['metrics']['var'] = var_result

            if var_result['var_pct'] > 5:
                report['issues'].append({
                    'type': 'high_var',
                    'message': f'VaR过高: {var_result["var_pct"]:.2f}%，潜在损失 ¥{var_result["var"]:,.2f}'
                })
                report['risk_level'] = 'HIGH'

        # 2. 集中度分析
        concentration = self.check_concentration_risk()
        report['metrics']['concentration'] = {
            'hhi': concentration['hhi'],
            'max_weight': concentration['max_weight'],
            'weights': concentration['weights']
        }

        for issue in concentration['issues']:
            report['issues'].append(issue)
            if issue['type'] == 'over_concentration':
                report['risk_level'] = max(report['risk_level'], 'MEDIUM', key=lambda x: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].index(x))

        for warning in concentration['warnings']:
            report['warnings'].append(warning)

        # 3. 跟踪止损检查
        stop_triggers = self.check_trailing_stop_triggers()
        report['metrics']['trailing_stops'] = {
            'triggered_count': len(stop_triggers),
            'triggered_stocks': stop_triggers
        }

        if stop_triggers:
            for trigger in stop_triggers:
                report['issues'].append({
                    'type': 'trailing_stop_triggered',
                    'code': trigger['code'],
                    'message': trigger['message']
                })
            report['risk_level'] = 'CRITICAL'

        # 4. 杠杆检查
        leverage_result = self.calculate_leverage(total_equity)
        report['metrics']['leverage'] = leverage_result

        if leverage_result['is_overleveraged']:
            report['issues'].append({
                'type': 'overleveraged',
                'message': leverage_result['message']
            })
            report['risk_level'] = max(report['risk_level'], 'HIGH', key=lambda x: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].index(x))

        # 5. 保证金检查
        margin_result = self.margin_call_check(total_equity)
        report['metrics']['margin'] = margin_result

        if margin_result['status'] == 'MARGIN_CALL':
            report['issues'].append({
                'type': 'margin_call',
                'message': margin_result['message']
            })
            report['risk_level'] = 'CRITICAL'
        elif margin_result['status'] == 'WARNING':
            report['warnings'].append({
                'type': 'margin_warning',
                'message': margin_result['message']
            })

        # 记录风险警报
        if report['issues']:
            self.risk_history['alerts'].append({
                'date': report['timestamp'],
                'risk_level': report['risk_level'],
                'issues_count': len(report['issues'])
            })
            self._save_risk_history()

        # 日志记录
        self.logger.info(f"综合风险检查完成，风险等级: {report['risk_level']}")
        if report['issues']:
            for issue in report['issues']:
                self.logger.warning(f"风险问题: {issue['message']}")

        return report

    def generate_risk_report_html(self, report: Dict = None, output_file: str = None) -> str:
        """
        生成HTML风险报告

        参数:
            report: 风险报告（None则生成新的）
            output_file: 输出文件路径

        返回:
            报告文件路径
        """
        if report is None:
            report = self.comprehensive_risk_check()

        if output_file is None:
            output_dir = Path(__file__).parent / "reports"
            output_dir.mkdir(exist_ok=True)
            output_file = str(output_dir / f"risk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

        risk_colors = {
            'LOW': '#10b981',
            'MEDIUM': '#f59e0b',
            'HIGH': '#ef4444',
            'CRITICAL': '#dc2626'
        }

        risk_color = risk_colors.get(report['risk_level'], '#666')

        html_content = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>风险管理报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f7fa;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{
            background: {risk_color};
            color: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
        }}
        .header h1 {{ margin: 0; font-size: 32px; }}
        .risk-badge {{
            display: inline-block;
            padding: 10px 30px;
            background: rgba(255,255,255,0.2);
            border-radius: 20px;
            margin-top: 15px;
            font-size: 24px;
            font-weight: bold;
        }}
        .section {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-top: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .metric-row {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: 600; }}
        .issue {{
            background: #fee2e2;
            border-left: 4px solid #ef4444;
            padding: 12px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .warning {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 12px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .card {{
            background: #f8fafc;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .card-value {{ font-size: 24px; font-weight: bold; color: #333; }}
        .card-label {{ font-size: 14px; color: #666; margin-top: 5px; }}
        .footer {{ text-align: center; color: #999; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ 风险管理报告</h1>
            <div class="risk-badge">风险等级: {report['risk_level']}</div>
            <p style="opacity:0.9; margin-top:10px;">{report['timestamp']}</p>
        </div>

        <div class="section">
            <div class="section-title">📊 关键指标</div>
            <div class="grid">
                <div class="card">
                    <div class="card-value">¥{report['portfolio_value']:,.0f}</div>
                    <div class="card-label">投资组合市值</div>
                </div>
                <div class="card">
                    <div class="card-value">{report['metrics'].get('var', {}).get('var_pct', 0):.2f}%</div>
                    <div class="card-label">VaR (95%)</div>
                </div>
                <div class="card">
                    <div class="card-value">{report['metrics'].get('concentration', {}).get('hhi', 0):.4f}</div>
                    <div class="card-label">HHI指数</div>
                </div>
                <div class="card">
                    <div class="card-value">{report['metrics'].get('leverage', {}).get('leverage', 1):.2f}x</div>
                    <div class="card-label">杠杆率</div>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">🚨 风险问题 ({len(report['issues'])})</div>
            {"".join([f'<div class="issue">❌ {issue["message"]}</div>' for issue in report['issues']]) if report['issues'] else '<p style="color:#666;">无重大风险问题</p>'}
        </div>

        <div class="section">
            <div class="section-title">⚠️ 风险警告 ({len(report['warnings'])})</div>
            {"".join([f'<div class="warning">⚠️ {warning["message"]}</div>' for warning in report['warnings']]) if report['warnings'] else '<p style="color:#666;">无风险警告</p>'}
        </div>

        <div class="section">
            <div class="section-title">📈 持仓权重分布</div>
            {"".join([f'<div class="metric-row"><span class="metric-label">{code}</span><span class="metric-value">{weight:.2%}</span></div>' for code, weight in report['metrics'].get('concentration', {}).get('weights', {}).items()])}
        </div>

        <div class="footer">
            自动化交易系统 - 风险管理报告
        </div>
    </div>
</body>
</html>
        '''

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.logger.info(f"风险报告已生成: {output_file}")
        return output_file

    def print_risk_summary(self, report: Dict = None):
        """打印风险摘要"""
        if report is None:
            report = self.comprehensive_risk_check()

        risk_icons = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🟠',
            'CRITICAL': '🔴'
        }

        print("\n" + "=" * 60)
        print(f"⚠️ 风险管理报告 - {report['timestamp']}")
        print("=" * 60)

        print(f"\n{risk_icons.get(report['risk_level'], '❓')} 风险等级: {report['risk_level']}")
        print(f"💰 投资组合市值: ¥{report['portfolio_value']:,.2f}")

        # VaR
        var_info = report['metrics'].get('var', {})
        if var_info:
            print(f"\n📊 VaR分析 ({var_info.get('confidence', 0.95):.0%} 置信度):")
            print(f"   日VaR: {var_info.get('var_pct', 0):.2f}% (¥{var_info.get('var', 0):,.2f})")
            print(f"   日CVaR: {var_info.get('cvar_pct', 0):.2f}% (¥{var_info.get('cvar', 0):,.2f})")

        # 集中度
        conc = report['metrics'].get('concentration', {})
        if conc:
            print(f"\n🎯 集中度分析:")
            print(f"   HHI指数: {conc.get('hhi', 0):.4f}")
            print(f"   最大权重: {conc.get('max_weight', 0):.2%} ({conc.get('max_weight_code', 'N/A')})")

        # 杠杆
        lev = report['metrics'].get('leverage', {})
        if lev:
            print(f"\n⚖️ 杠杆状态:")
            print(f"   当前杠杆: {lev.get('leverage', 1):.2f}x")
            print(f"   状态: {'超限' if lev.get('is_overleveraged') else '正常'}")

        # 问题和警告
        if report['issues']:
            print(f"\n🚨 风险问题 ({len(report['issues'])} 个):")
            for issue in report['issues']:
                print(f"   ❌ {issue['message']}")

        if report['warnings']:
            print(f"\n⚠️ 风险警告 ({len(report['warnings'])} 个):")
            for warning in report['warnings']:
                print(f"   ⚠️ {warning['message']}")

        print("\n" + "=" * 60)


def demo():
    """演示风险管理功能"""
    print("\n" + "=" * 60)
    print("🛡️ 高级风险管理模块演示")
    print("=" * 60)

    # 创建模拟数据
    np.random.seed(42)

    # 模拟持仓
    positions = {
        'SH600000': {'shares': 5000, 'avg_cost': 12.0, 'current_price': 11.5},
        'SH600036': {'shares': 3000, 'avg_cost': 35.0, 'current_price': 38.0},
        'SH601318': {'shares': 2000, 'avg_cost': 50.0, 'current_price': 48.0}
    }

    # 模拟价格历史
    price_history = {}
    for code in positions.keys():
        base_price = positions[code]['current_price']
        prices = base_price * (1 + np.cumsum(np.random.normal(0.001, 0.02, 100)))
        prices[-1] = positions[code]['current_price']  # 确保最后一个是当前价格
        price_history[code] = pd.Series(prices)

    # 创建风险管理器
    rm = RiskManager()
    rm.set_portfolio(positions, price_history)

    # 计算投资组合价值
    portfolio_value = rm.calculate_portfolio_value()
    print(f"\n💰 投资组合市值: ¥{portfolio_value:,.2f}")

    # VaR分析
    print("\n📊 VaR分析...")
    var_result = rm.calculate_portfolio_var()
    print(f"   95% VaR: {var_result['var_pct']:.2f}% (¥{var_result['var']:,.2f})")
    print(f"   95% CVaR: {var_result['cvar_pct']:.2f}% (¥{var_result['cvar']:,.2f})")

    # 相关性分析
    print("\n🔗 相关性矩阵:")
    corr_matrix = rm.calculate_correlation_matrix()
    print(corr_matrix.round(3))

    # 集中度风险
    print("\n🎯 集中度分析:")
    concentration = rm.check_concentration_risk()
    for code, weight in concentration['weights'].items():
        print(f"   {code}: {weight:.2%}")
    print(f"   HHI指数: {concentration['hhi']:.4f}")

    # 跟踪止损
    print("\n🛑 跟踪止损检查:")
    triggered = rm.check_trailing_stop_triggers()
    if triggered:
        for t in triggered:
            print(f"   ❌ {t['message']}")
    else:
        print("   ✅ 无止损触发")

    # 杠杆检查
    print("\n⚖️ 杠杆状态:")
    leverage = rm.calculate_leverage(portfolio_value * 0.8)  # 假设有20%借款
    print(f"   杠杆率: {leverage['leverage']:.2f}x")
    print(f"   状态: {leverage['message']}")

    # 综合风险报告
    print("\n📋 生成综合风险报告...")
    report = rm.comprehensive_risk_check(portfolio_value)
    rm.print_risk_summary(report)

    # 生成HTML报告
    print("\n📄 生成HTML报告...")
    report_file = rm.generate_risk_report_html(report)
    print(f"   报告已保存: {report_file}")

    print("\n" + "=" * 60)
    print("✅ 风险管理演示完成")
    print("=" * 60)


if __name__ == '__main__':
    demo()
