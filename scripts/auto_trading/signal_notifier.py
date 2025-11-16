#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易信号邮件通知系统

每日收盘后运行，检测交易信号并发送邮件报告。

功能：
- 运行多个策略检测信号
- 检查持仓风险（止损/止盈）
- 生成HTML格式邮件报告
- 通过QQ邮箱/163邮箱/Gmail发送

使用方法:
    # 配置邮箱（首次使用）
    python signal_notifier.py --setup

    # 手动运行检测并发送邮件
    python signal_notifier.py --run

    # 设置定时任务（每天16:00）
    0 16 * * 1-5 cd /path/to/auto_trading && python signal_notifier.py --run
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import argparse

# 添加路径
sys.path.append(str(Path(__file__).parent))

from portfolio_management import PortfolioManager
from strategies.dual_ma_strategy import DualMAStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy


class SignalNotifier:
    """
    交易信号通知器
    """

    def __init__(self, config_path: str = None):
        """
        初始化通知器

        参数:
            config_path: 配置文件路径
        """
        if config_path is None:
            config_path = str(Path(__file__).parent / "email_config.json")

        self.config_path = config_path
        self.config = self._load_config()

        # 信号阈值
        self.buy_score_threshold = 75  # 买入评分阈值
        self.sell_score_threshold = 40  # 卖出评分阈值
        self.take_profit_threshold = 0.15  # 止盈线 15%
        self.stop_loss_threshold = -0.08  # 止损线 -8%
        self.min_consensus = 2  # 最少策略共识数

        # 持仓管理器
        self.portfolio_manager = PortfolioManager()

    def _load_config(self) -> dict:
        """加载邮箱配置"""
        if Path(self.config_path).exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}

    def _save_config(self, config: dict):
        """保存邮箱配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ 配置已保存: {self.config_path}")

    def setup_email(self):
        """设置邮箱配置（交互式）"""
        print("\n" + "=" * 60)
        print("📧 邮箱配置向导")
        print("=" * 60)

        print("\n请选择邮箱类型：")
        print("1. QQ邮箱")
        print("2. 163邮箱")
        print("3. Gmail")
        print("4. 自定义SMTP")

        choice = input("\n选择 [1-4]: ").strip()

        if choice == '1':
            smtp_server = 'smtp.qq.com'
            smtp_port = 465
            use_ssl = True
            print("\n📌 QQ邮箱配置说明：")
            print("1. 登录QQ邮箱 → 设置 → 账户")
            print("2. 开启 'POP3/SMTP服务'")
            print("3. 生成授权码（不是QQ密码！）")
        elif choice == '2':
            smtp_server = 'smtp.163.com'
            smtp_port = 465
            use_ssl = True
            print("\n📌 163邮箱配置说明：")
            print("1. 登录163邮箱 → 设置 → POP3/SMTP/IMAP")
            print("2. 开启SMTP服务")
            print("3. 设置授权码")
        elif choice == '3':
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
            use_ssl = False
            print("\n📌 Gmail配置说明：")
            print("1. 开启两步验证")
            print("2. 生成应用专用密码")
        else:
            smtp_server = input("SMTP服务器: ").strip()
            smtp_port = int(input("端口号: ").strip())
            use_ssl = input("使用SSL? (y/n): ").lower() == 'y'

        sender_email = input("\n发件人邮箱: ").strip()
        auth_code = input("授权码/密码: ").strip()
        receiver_email = input("收件人邮箱（接收通知）: ").strip()

        config = {
            'smtp_server': smtp_server,
            'smtp_port': smtp_port,
            'use_ssl': use_ssl,
            'sender_email': sender_email,
            'auth_code': auth_code,
            'receiver_email': receiver_email
        }

        # 测试连接
        print("\n🔄 测试邮箱连接...")
        if self._test_email_connection(config):
            self._save_config(config)
            self.config = config
            print("✅ 邮箱配置成功！")

            # 发送测试邮件
            if input("\n发送测试邮件? (y/n): ").lower() == 'y':
                self.send_test_email()
        else:
            print("❌ 邮箱连接失败，请检查配置")

    def _test_email_connection(self, config: dict) -> bool:
        """测试邮箱连接"""
        try:
            if config['use_ssl']:
                server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=10)
            else:
                server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=10)
                server.starttls()

            server.login(config['sender_email'], config['auth_code'])
            server.quit()
            return True
        except Exception as e:
            print(f"连接错误: {str(e)}")
            return False

    def send_test_email(self):
        """发送测试邮件"""
        subject = "📊 交易信号通知系统 - 测试邮件"
        content = """
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>🎉 恭喜！邮件配置成功</h2>
            <p>您的交易信号通知系统已配置完成。</p>
            <p>系统将在每个交易日收盘后（16:00）自动运行，检测交易信号并发送报告。</p>
            <hr>
            <p style="color: #888;">发送时间: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </body>
        </html>
        """
        self._send_email(subject, content)

    def _send_email(self, subject: str, html_content: str):
        """
        发送邮件

        参数:
            subject: 邮件主题
            html_content: HTML格式的邮件内容
        """
        if not self.config:
            print("❌ 邮箱未配置，请先运行 --setup")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = self.config['sender_email']
            msg['To'] = self.config['receiver_email']

            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            if self.config['use_ssl']:
                server = smtplib.SMTP_SSL(self.config['smtp_server'], self.config['smtp_port'])
            else:
                server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
                server.starttls()

            server.login(self.config['sender_email'], self.config['auth_code'])
            server.sendmail(
                self.config['sender_email'],
                self.config['receiver_email'],
                msg.as_string()
            )
            server.quit()

            print(f"✅ 邮件已发送至 {self.config['receiver_email']}")
            return True

        except Exception as e:
            print(f"❌ 邮件发送失败: {str(e)}")
            return False

    def generate_demo_market_data(self, n_stocks: int = 30, n_days: int = 100) -> pd.DataFrame:
        """生成模拟市场数据（用于演示）"""
        np.random.seed(int(datetime.now().timestamp()) % 1000)
        dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
        date_strs = dates.strftime('%Y-%m-%d').tolist()

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
            trend = np.random.uniform(-0.001, 0.002)
            volatility = np.random.uniform(0.015, 0.035)

            prices = np.zeros(n_days)
            prices[0] = initial_price
            for j in range(1, n_days):
                change = np.random.normal(trend, volatility)
                prices[j] = max(prices[j-1] * (1 + change), 1)

            daily_vols = volatility * prices
            open_prices = prices + np.random.normal(0, daily_vols * 0.5)
            high_prices = np.maximum(open_prices, prices) + np.abs(np.random.normal(0, daily_vols * 0.3))
            low_prices = np.minimum(open_prices, prices) - np.abs(np.random.normal(0, daily_vols * 0.3))
            stock_volumes = np.random.uniform(1e6, 1e8, n_days)

            end_idx = idx + n_days
            codes.extend([code] * n_days)
            all_dates.extend(date_strs)
            opens[idx:end_idx] = np.round(open_prices, 2)
            highs[idx:end_idx] = np.round(high_prices, 2)
            lows[idx:end_idx] = np.round(low_prices, 2)
            closes[idx:end_idx] = np.round(prices, 2)
            volumes[idx:end_idx] = stock_volumes.astype(int)
            idx = end_idx

        return pd.DataFrame({
            'code': codes,
            'date': all_dates,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes.astype(int)
        })

    def detect_signals(self, market_data: pd.DataFrame = None) -> dict:
        """
        检测交易信号

        参数:
            market_data: 市场数据，如果为None则生成模拟数据

        返回:
            {'buy_signals': [], 'sell_signals': [], 'watch_signals': [], 'portfolio_alerts': []}
        """
        print("🔍 检测交易信号...")

        if market_data is None:
            print("  使用模拟数据演示...")
            market_data = self.generate_demo_market_data()

        # 获取最新日期
        latest_date = market_data['date'].max()
        print(f"  数据日期: {latest_date}")

        # 运行多个策略
        strategies = {
            'DualMA_5_20': DualMAStrategy(short_window=5, long_window=20),
            'Momentum_20d': MomentumStrategy(lookback_period=20),
            'MeanReversion_20d': MeanReversionStrategy(window=20)
        }

        all_signals = {}
        for name, strategy in strategies.items():
            print(f"  运行 {name} 策略...")
            try:
                result = strategy.generate_daily_signals(market_data, latest_date, topk=50)
                signals = result['signals']
                if not signals.empty:
                    for _, row in signals.iterrows():
                        code = row['code']
                        if code not in all_signals:
                            all_signals[code] = {
                                'scores': [],
                                'strategies': [],
                                'signal': 0
                            }
                        all_signals[code]['scores'].append(row['score'])
                        all_signals[code]['strategies'].append(name)
                        if row['signal'] > 0:
                            all_signals[code]['signal'] += 1
            except Exception as e:
                print(f"    ⚠️ {name} 失败: {str(e)[:30]}")

        # 分析信号
        buy_signals = []
        sell_signals = []
        watch_signals = []

        for code, data in all_signals.items():
            avg_score = np.mean(data['scores'])
            consensus = data['signal']
            strategies_list = ', '.join(data['strategies'])

            # 获取最新价格
            latest_price = market_data[
                (market_data['code'] == code) & (market_data['date'] == latest_date)
            ]['close'].values

            price = latest_price[0] if len(latest_price) > 0 else 0

            signal_info = {
                'code': code,
                'score': avg_score,
                'consensus': consensus,
                'strategies': strategies_list,
                'price': price
            }

            # 买入信号判断
            if avg_score >= self.buy_score_threshold or consensus >= self.min_consensus:
                buy_signals.append(signal_info)
            # 关注信号
            elif avg_score >= 65:
                watch_signals.append(signal_info)

        # 检查持仓风险
        portfolio_alerts = self._check_portfolio_risks()

        # 排序
        buy_signals = sorted(buy_signals, key=lambda x: x['score'], reverse=True)[:10]
        watch_signals = sorted(watch_signals, key=lambda x: x['score'], reverse=True)[:5]

        print(f"  ✅ 发现 {len(buy_signals)} 个买入信号, {len(portfolio_alerts)} 个持仓提醒")

        return {
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'watch_signals': watch_signals,
            'portfolio_alerts': portfolio_alerts,
            'date': latest_date
        }

    def _check_portfolio_risks(self) -> list:
        """检查持仓风险"""
        alerts = []

        try:
            positions = self.portfolio_manager.get_all_positions()

            for _, pos in positions.iterrows():
                profit_pct = pos['profit_pct'] / 100

                # 止盈提醒
                if profit_pct >= self.take_profit_threshold:
                    alerts.append({
                        'code': pos['code'],
                        'name': pos['name'],
                        'type': 'take_profit',
                        'profit_pct': pos['profit_pct'],
                        'shares': pos['shares'],
                        'current_price': pos['current_price'],
                        'message': f"🎯 止盈提醒: 已盈利 {pos['profit_pct']:.1f}%"
                    })

                # 止损提醒
                elif profit_pct <= self.stop_loss_threshold:
                    alerts.append({
                        'code': pos['code'],
                        'name': pos['name'],
                        'type': 'stop_loss',
                        'profit_pct': pos['profit_pct'],
                        'shares': pos['shares'],
                        'current_price': pos['current_price'],
                        'message': f"⚠️ 止损提醒: 已亏损 {pos['profit_pct']:.1f}%"
                    })

                # 接近止盈
                elif profit_pct >= 0.10:
                    alerts.append({
                        'code': pos['code'],
                        'name': pos['name'],
                        'type': 'near_take_profit',
                        'profit_pct': pos['profit_pct'],
                        'shares': pos['shares'],
                        'current_price': pos['current_price'],
                        'message': f"📈 接近止盈: 已盈利 {pos['profit_pct']:.1f}%"
                    })

                # 接近止损
                elif profit_pct <= -0.05:
                    alerts.append({
                        'code': pos['code'],
                        'name': pos['name'],
                        'type': 'near_stop_loss',
                        'profit_pct': pos['profit_pct'],
                        'shares': pos['shares'],
                        'current_price': pos['current_price'],
                        'message': f"📉 接近止损: 已亏损 {pos['profit_pct']:.1f}%"
                    })

        except Exception as e:
            print(f"  ⚠️ 检查持仓风险失败: {str(e)}")

        return alerts

    def generate_email_report(self, signals: dict) -> str:
        """
        生成HTML格式的邮件报告

        参数:
            signals: 信号检测结果

        返回:
            HTML内容
        """
        date = signals.get('date', datetime.now().strftime('%Y-%m-%d'))

        html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 25px; }}
        .signal-card {{ background: #ecf0f1; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #3498db; }}
        .signal-card.buy {{ border-left-color: #27ae60; background: #d4edda; }}
        .signal-card.sell {{ border-left-color: #e74c3c; background: #f8d7da; }}
        .signal-card.watch {{ border-left-color: #f39c12; background: #fff3cd; }}
        .signal-card.alert {{ border-left-color: #e74c3c; background: #ffeaa7; }}
        .code {{ font-size: 18px; font-weight: bold; color: #2c3e50; }}
        .score {{ font-size: 24px; font-weight: bold; color: #27ae60; }}
        .detail {{ color: #7f8c8d; font-size: 14px; margin-top: 5px; }}
        .summary-box {{ background: #3498db; color: white; padding: 15px; border-radius: 8px; margin: 10px 0; }}
        .no-signal {{ color: #7f8c8d; font-style: italic; }}
        .timestamp {{ color: #95a5a6; font-size: 12px; text-align: right; margin-top: 20px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 每日交易信号报告</h1>
        <div class="summary-box">
            <strong>报告日期:</strong> {date}<br>
            <strong>买入信号:</strong> {len(signals['buy_signals'])} 个<br>
            <strong>持仓提醒:</strong> {len(signals['portfolio_alerts'])} 个<br>
            <strong>关注股票:</strong> {len(signals['watch_signals'])} 个
        </div>
'''

        # 买入信号
        html += '<h2>🟢 买入信号</h2>'
        if signals['buy_signals']:
            for sig in signals['buy_signals'][:5]:  # 最多显示5个
                html += f'''
        <div class="signal-card buy">
            <div class="code">{sig['code']}</div>
            <div class="score">评分: {sig['score']:.1f}</div>
            <div class="detail">
                当前价格: ¥{sig['price']:.2f}<br>
                策略共识: {sig['consensus']} 个策略看涨<br>
                推荐策略: {sig['strategies']}
            </div>
        </div>
'''
        else:
            html += '<p class="no-signal">今日无强烈买入信号</p>'

        # 持仓提醒
        html += '<h2>⚠️ 持仓风险提醒</h2>'
        if signals['portfolio_alerts']:
            for alert in signals['portfolio_alerts']:
                html += f'''
        <div class="signal-card alert">
            <div class="code">{alert['code']} {alert.get('name', '')}</div>
            <div class="detail">
                {alert['message']}<br>
                持有: {alert['shares']:,} 股<br>
                当前价格: ¥{alert['current_price']:.2f}
            </div>
        </div>
'''
        else:
            html += '<p class="no-signal">持仓状态良好，无风险提醒</p>'

        # 关注信号
        html += '<h2>👀 关注信号</h2>'
        if signals['watch_signals']:
            for sig in signals['watch_signals'][:3]:
                html += f'''
        <div class="signal-card watch">
            <div class="code">{sig['code']}</div>
            <div class="detail">
                评分: {sig['score']:.1f} | 价格: ¥{sig['price']:.2f}<br>
                策略: {sig['strategies']}
            </div>
        </div>
'''
        else:
            html += '<p class="no-signal">无关注信号</p>'

        # 账户概览
        try:
            account = self.portfolio_manager.get_account_info()
            html += f'''
        <h2>💰 账户概览</h2>
        <div class="signal-card">
            <div class="detail">
                总资产: ¥{account['total_value']:,.2f}<br>
                现金: ¥{account['cash']:,.2f}<br>
                持仓市值: ¥{account['positions_value']:,.2f}<br>
                总盈亏: ¥{account['total_pnl']:,.2f} ({account['total_pnl_pct']:+.2f}%)
            </div>
        </div>
'''
        except:
            pass

        html += f'''
        <div class="footer">
            <p>⚠️ 风险提示：本报告仅供参考，不构成投资建议。市场有风险，投资需谨慎。</p>
            <p>历史表现不代表未来收益，请根据自身情况谨慎决策。</p>
        </div>

        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
'''
        return html

    def run_daily_check(self, market_data: pd.DataFrame = None):
        """
        运行每日信号检测并发送邮件

        参数:
            market_data: 市场数据（可选）
        """
        print("\n" + "=" * 60)
        print("📧 每日交易信号检测")
        print("=" * 60)
        print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 检测信号
        signals = self.detect_signals(market_data)

        # 判断是否需要发送邮件
        has_important_signal = (
            len(signals['buy_signals']) > 0 or
            len(signals['portfolio_alerts']) > 0
        )

        if has_important_signal:
            print("\n📨 发现重要信号，准备发送邮件...")

            # 生成报告
            html_report = self.generate_email_report(signals)

            # 发送邮件
            subject = f"📊 交易信号报告 - {signals['date']}"
            if len(signals['buy_signals']) > 0:
                subject += f" | {len(signals['buy_signals'])}个买入信号"
            if len(signals['portfolio_alerts']) > 0:
                subject += f" | {len(signals['portfolio_alerts'])}个风险提醒"

            self._send_email(subject, html_report)

            # 保存报告副本
            report_path = Path(__file__).parent / "reports" / f"signal_report_{signals['date']}.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_report)
            print(f"✅ 报告已保存: {report_path}")

        else:
            print("\n📭 今日无重要信号，跳过邮件发送")
            print("  （如需强制发送，请使用 --force 参数）")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description='交易信号邮件通知系统')
    parser.add_argument('--setup', action='store_true', help='配置邮箱')
    parser.add_argument('--run', action='store_true', help='运行信号检测并发送邮件')
    parser.add_argument('--test', action='store_true', help='发送测试邮件')
    parser.add_argument('--force', action='store_true', help='强制发送邮件（即使无信号）')
    parser.add_argument('--demo', action='store_true', help='使用演示数据（无需真实行情）')

    args = parser.parse_args()

    notifier = SignalNotifier()

    if args.setup:
        notifier.setup_email()

    elif args.test:
        notifier.send_test_email()

    elif args.run or args.demo:
        if args.demo:
            # 使用演示数据
            notifier.run_daily_check(market_data=None)
        else:
            # 尝试获取真实数据（未实现，使用演示数据）
            print("⚠️ 真实数据获取暂未集成，使用演示数据")
            notifier.run_daily_check(market_data=None)

    else:
        print("交易信号邮件通知系统")
        print("=" * 40)
        print("使用方法:")
        print("  --setup  配置邮箱（首次使用）")
        print("  --test   发送测试邮件")
        print("  --run    运行信号检测并发送邮件")
        print("  --demo   使用演示数据测试")
        print()
        print("示例:")
        print("  python signal_notifier.py --setup")
        print("  python signal_notifier.py --demo")
        print()
        print("定时任务（每天16:00）:")
        print("  0 16 * * 1-5 cd /path/to && python signal_notifier.py --run")


if __name__ == '__main__':
    main()
