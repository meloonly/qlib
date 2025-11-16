#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web仪表盘

基于Flask的Web界面，用于：
- 查看持仓状态
- 查看交易信号
- 查看系统报告
- 可视化图表

使用方法:
    python web_dashboard.py
    然后在浏览器中访问 http://localhost:5000
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from flask import Flask, render_template_string, jsonify, request
except ImportError:
    print("请安装Flask: pip install flask")
    sys.exit(1)

from config_manager import ConfigManager
from portfolio_management import PortfolioManager
from signal_notifier import SignalNotifier
from logger import SystemLogger


app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 全局对象
config = ConfigManager()
logger = SystemLogger('web_dashboard')

# HTML模板
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>自动化交易系统 - 仪表盘</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 40px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header h1 {
            font-size: 28px;
            font-weight: 600;
        }
        .header .subtitle {
            opacity: 0.9;
            font-size: 14px;
            margin-top: 5px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        }
        .card-title {
            font-size: 16px;
            color: #666;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-value {
            font-size: 32px;
            font-weight: 700;
            color: #333;
        }
        .card-value.positive { color: #10b981; }
        .card-value.negative { color: #ef4444; }
        .card-change {
            font-size: 14px;
            margin-top: 8px;
        }
        .section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        .section-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f8fafc;
            font-weight: 600;
            color: #666;
            font-size: 14px;
        }
        tr:hover {
            background: #f8fafc;
        }
        .signal-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-buy {
            background: #dcfce7;
            color: #15803d;
        }
        .badge-sell {
            background: #fee2e2;
            color: #dc2626;
        }
        .badge-watch {
            background: #fef3c7;
            color: #d97706;
        }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
            font-size: 14px;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5a67d8;
        }
        .btn-secondary {
            background: #e2e8f0;
            color: #475569;
        }
        .btn-secondary:hover {
            background: #cbd5e1;
        }
        .chart-container {
            height: 300px;
            background: #f8fafc;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #999;
        }
        .nav {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .alert-warning {
            background: #fef3c7;
            color: #92400e;
            border-left: 4px solid #f59e0b;
        }
        .alert-danger {
            background: #fee2e2;
            color: #991b1b;
            border-left: 4px solid #ef4444;
        }
        .alert-info {
            background: #dbeafe;
            color: #1e40af;
            border-left: 4px solid #3b82f6;
        }
        .timestamp {
            color: #999;
            font-size: 12px;
            margin-top: 10px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        @media (max-width: 768px) {
            .container { padding: 15px; }
            .header { padding: 15px 20px; }
            .card-value { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 自动化交易系统</h1>
        <div class="subtitle">实时监控 · 智能分析 · 风险控制</div>
    </div>

    <div class="container">
        <div class="nav">
            <button class="btn btn-primary" onclick="refreshData()">🔄 刷新数据</button>
            <button class="btn btn-secondary" onclick="detectSignals()">🔍 检测信号</button>
            <button class="btn btn-secondary" onclick="window.location.href='/api/export'">📥 导出报告</button>
        </div>

        <div id="alerts"></div>

        <div class="grid">
            <div class="card">
                <div class="card-title">💰 总资产</div>
                <div class="card-value" id="total-value">加载中...</div>
                <div class="card-change" id="total-pnl"></div>
            </div>
            <div class="card">
                <div class="card-title">💵 可用现金</div>
                <div class="card-value" id="cash">加载中...</div>
                <div class="card-change" id="cash-ratio"></div>
            </div>
            <div class="card">
                <div class="card-title">📈 持仓市值</div>
                <div class="card-value" id="positions-value">加载中...</div>
                <div class="card-change" id="positions-count"></div>
            </div>
            <div class="card">
                <div class="card-title">🎯 买入信号</div>
                <div class="card-value" id="buy-signals">-</div>
                <div class="card-change" id="signal-time"></div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">💼 当前持仓</div>
            <div id="positions-table">
                <div class="loading">加载中...</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">🔔 交易信号</div>
            <div id="signals-table">
                <div class="loading">点击"检测信号"获取最新信号</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">📜 最近交易</div>
            <div id="trades-table">
                <div class="loading">加载中...</div>
            </div>
        </div>

        <div class="timestamp" id="last-update"></div>
    </div>

    <script>
        function formatNumber(num) {
            return new Intl.NumberFormat('zh-CN', {
                style: 'currency',
                currency: 'CNY',
                minimumFractionDigits: 2
            }).format(num);
        }

        function formatPercent(num) {
            const sign = num >= 0 ? '+' : '';
            return sign + num.toFixed(2) + '%';
        }

        async function refreshData() {
            try {
                const response = await fetch('/api/portfolio');
                const data = await response.json();

                if (data.success) {
                    const account = data.account;
                    document.getElementById('total-value').textContent = formatNumber(account.total_value);
                    document.getElementById('total-value').className = 'card-value ' + (account.total_pnl_pct >= 0 ? 'positive' : 'negative');
                    document.getElementById('total-pnl').textContent = formatPercent(account.total_pnl_pct);
                    document.getElementById('cash').textContent = formatNumber(account.cash);
                    document.getElementById('cash-ratio').textContent = '现金比例: ' + ((account.cash / account.total_value) * 100).toFixed(1) + '%';
                    document.getElementById('positions-value').textContent = formatNumber(account.positions_value);
                    document.getElementById('positions-count').textContent = data.positions.length + ' 只股票';

                    // 持仓表格
                    if (data.positions.length > 0) {
                        let tableHtml = '<table><thead><tr><th>股票代码</th><th>持仓数量</th><th>成本价</th><th>现价</th><th>市值</th><th>盈亏</th><th>盈亏%</th></tr></thead><tbody>';
                        data.positions.forEach(pos => {
                            const pnlClass = pos.profit_pct >= 0 ? 'positive' : 'negative';
                            tableHtml += `<tr>
                                <td><strong>${pos.code}</strong></td>
                                <td>${pos.shares}</td>
                                <td>¥${pos.avg_cost.toFixed(2)}</td>
                                <td>¥${pos.current_price.toFixed(2)}</td>
                                <td>¥${pos.market_value.toFixed(2)}</td>
                                <td class="${pnlClass}">¥${pos.profit.toFixed(2)}</td>
                                <td class="${pnlClass}">${formatPercent(pos.profit_pct)}</td>
                            </tr>`;
                        });
                        tableHtml += '</tbody></table>';
                        document.getElementById('positions-table').innerHTML = tableHtml;
                    } else {
                        document.getElementById('positions-table').innerHTML = '<div class="loading">暂无持仓</div>';
                    }

                    // 交易记录
                    if (data.recent_trades.length > 0) {
                        let tradesHtml = '<table><thead><tr><th>时间</th><th>类型</th><th>股票</th><th>数量</th><th>价格</th><th>金额</th></tr></thead><tbody>';
                        data.recent_trades.forEach(trade => {
                            const typeClass = trade.type === 'buy' ? 'badge-buy' : 'badge-sell';
                            const typeText = trade.type === 'buy' ? '买入' : '卖出';
                            tradesHtml += `<tr>
                                <td>${trade.time}</td>
                                <td><span class="signal-badge ${typeClass}">${typeText}</span></td>
                                <td>${trade.code}</td>
                                <td>${trade.shares}</td>
                                <td>¥${trade.price.toFixed(2)}</td>
                                <td>¥${trade.amount.toFixed(2)}</td>
                            </tr>`;
                        });
                        tradesHtml += '</tbody></table>';
                        document.getElementById('trades-table').innerHTML = tradesHtml;
                    } else {
                        document.getElementById('trades-table').innerHTML = '<div class="loading">暂无交易记录</div>';
                    }

                    // 风险提醒
                    let alertsHtml = '';
                    if (data.alerts && data.alerts.length > 0) {
                        data.alerts.forEach(alert => {
                            const alertClass = alert.type === 'stop_loss' ? 'alert-danger' : 'alert-warning';
                            alertsHtml += `<div class="alert ${alertClass}">${alert.message}</div>`;
                        });
                    }
                    document.getElementById('alerts').innerHTML = alertsHtml;
                }

                document.getElementById('last-update').textContent = '最后更新: ' + new Date().toLocaleString('zh-CN');
            } catch (error) {
                console.error('刷新数据失败:', error);
            }
        }

        async function detectSignals() {
            document.getElementById('signals-table').innerHTML = '<div class="loading">正在检测信号...</div>';

            try {
                const response = await fetch('/api/signals');
                const data = await response.json();

                if (data.success) {
                    document.getElementById('buy-signals').textContent = data.buy_count;
                    document.getElementById('signal-time').textContent = '更新于: ' + new Date().toLocaleTimeString('zh-CN');

                    let signalsHtml = '';

                    if (data.buy_signals.length > 0) {
                        signalsHtml += '<h4 style="margin: 10px 0;">🟢 买入信号</h4>';
                        signalsHtml += '<table><thead><tr><th>股票代码</th><th>评分</th><th>策略数</th><th>原因</th></tr></thead><tbody>';
                        data.buy_signals.forEach(signal => {
                            signalsHtml += `<tr>
                                <td><strong>${signal.code}</strong></td>
                                <td>${signal.score.toFixed(1)}</td>
                                <td>${signal.strategies}</td>
                                <td>${signal.reasons.join(', ')}</td>
                            </tr>`;
                        });
                        signalsHtml += '</tbody></table>';
                    }

                    if (data.watch_signals.length > 0) {
                        signalsHtml += '<h4 style="margin: 20px 0 10px;">🟡 关注信号</h4>';
                        signalsHtml += '<table><thead><tr><th>股票代码</th><th>评分</th><th>策略数</th></tr></thead><tbody>';
                        data.watch_signals.forEach(signal => {
                            signalsHtml += `<tr>
                                <td>${signal.code}</td>
                                <td>${signal.score.toFixed(1)}</td>
                                <td>${signal.strategies}</td>
                            </tr>`;
                        });
                        signalsHtml += '</tbody></table>';
                    }

                    if (signalsHtml === '') {
                        signalsHtml = '<div class="loading">暂无交易信号</div>';
                    }

                    document.getElementById('signals-table').innerHTML = signalsHtml;
                } else {
                    document.getElementById('signals-table').innerHTML = '<div class="alert alert-danger">信号检测失败: ' + data.error + '</div>';
                }
            } catch (error) {
                document.getElementById('signals-table').innerHTML = '<div class="alert alert-danger">请求失败: ' + error.message + '</div>';
            }
        }

        // 页面加载时刷新数据
        refreshData();

        // 每5分钟自动刷新
        setInterval(refreshData, 300000);
    </script>
</body>
</html>
'''


@app.route('/')
def dashboard():
    """主页 - 仪表盘"""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/portfolio')
def get_portfolio():
    """获取投资组合数据"""
    try:
        pm = PortfolioManager()
        account = pm.get_account_info()
        positions = pm.get_positions()
        trades = pm.get_trade_history(limit=10)

        # 检查风险
        alerts = []
        risk_params = config.get_risk_params()
        stop_loss = risk_params.get('stop_loss_threshold', -0.08)
        take_profit = risk_params.get('take_profit_threshold', 0.15)

        positions_list = []
        for pos in positions:
            code, shares, avg_cost, current_price, market_value, profit, profit_pct, last_update = pos
            positions_list.append({
                'code': code,
                'shares': shares,
                'avg_cost': avg_cost,
                'current_price': current_price,
                'market_value': market_value,
                'profit': profit,
                'profit_pct': profit_pct,
                'last_update': last_update
            })

            # 检查止损止盈
            if profit_pct <= stop_loss * 100:
                alerts.append({
                    'type': 'stop_loss',
                    'message': f'⚠️ {code} 触及止损线，当前亏损 {profit_pct:.2f}%，建议止损'
                })
            elif profit_pct >= take_profit * 100:
                alerts.append({
                    'type': 'take_profit',
                    'message': f'🎯 {code} 触及止盈线，当前盈利 {profit_pct:.2f}%，建议止盈'
                })

        # 处理交易记录
        trades_list = []
        for trade in trades:
            trades_list.append({
                'time': trade[1],
                'type': trade[2],
                'code': trade[3],
                'shares': trade[4],
                'price': trade[5],
                'amount': trade[6]
            })

        return jsonify({
            'success': True,
            'account': account,
            'positions': positions_list,
            'recent_trades': trades_list,
            'alerts': alerts
        })
    except Exception as e:
        logger.log_exception(e, "获取投资组合数据")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/signals')
def get_signals():
    """检测并获取交易信号"""
    try:
        notifier = SignalNotifier()

        # 生成模拟数据进行信号检测
        import pandas as pd
        import numpy as np

        stocks = config.get_stock_pool()
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

        # 简单模拟数据
        np.random.seed(int(datetime.now().timestamp()) % 1000)
        data = pd.DataFrame(index=dates)

        for stock in stocks:
            initial_price = np.random.uniform(10, 100)
            returns = np.random.normal(0.001, 0.02, len(dates))
            prices = initial_price * (1 + returns).cumprod()
            data[stock] = prices

        # 检测信号
        signals = notifier.detect_signals(data)

        return jsonify({
            'success': True,
            'buy_count': len(signals.get('buy_signals', [])),
            'sell_count': len(signals.get('sell_signals', [])),
            'watch_count': len(signals.get('watch_signals', [])),
            'buy_signals': signals.get('buy_signals', []),
            'sell_signals': signals.get('sell_signals', []),
            'watch_signals': signals.get('watch_signals', [])
        })
    except Exception as e:
        logger.log_exception(e, "检测交易信号")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config')
def get_config():
    """获取系统配置"""
    try:
        return jsonify({
            'success': True,
            'config': {
                'risk_control': config.get_risk_params(),
                'strategies': config.get_enabled_strategies(),
                'stock_pool': config.get_stock_pool(),
                'signal_detection': config.get_signal_params()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/export')
def export_report():
    """导出报告"""
    try:
        pm = PortfolioManager()
        report_file = pm.generate_html_report()
        return jsonify({
            'success': True,
            'message': f'报告已导出: {report_file}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/system_status')
def get_system_status():
    """获取系统状态"""
    try:
        log_dir = Path(__file__).parent / "logs"
        log_files = list(log_dir.glob("*.log")) if log_dir.exists() else []
        total_log_size = sum(f.stat().st_size for f in log_files) / 1024 / 1024

        return jsonify({
            'success': True,
            'status': {
                'system_name': config.get('system.name'),
                'version': config.get('system.version'),
                'data_source': config.get('data_source.default'),
                'enabled_strategies': config.get_enabled_strategies(),
                'stock_pool_size': len(config.get_stock_pool()),
                'log_files_count': len(log_files),
                'log_size_mb': round(total_log_size, 2)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """启动Web仪表盘"""
    print("\n" + "=" * 60)
    print("🌐 启动Web仪表盘")
    print("=" * 60)
    print(f"访问地址: http://localhost:{port}")
    print(f"或: http://127.0.0.1:{port}")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60 + "\n")

    logger.info(f"Web仪表盘启动于 {host}:{port}")
    app.run(host=host, port=port, debug=debug)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='自动化交易系统 - Web仪表盘')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5000, help='监听端口')
    parser.add_argument('--debug', action='store_true', help='调试模式')

    args = parser.parse_args()
    run_dashboard(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
