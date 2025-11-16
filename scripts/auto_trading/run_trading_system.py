#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一启动脚本

一键运行整个交易系统:
数据更新 → 数据质量检查 → 信号检测 → 风险监控 → 邮件通知

使用方法:
    # 运行每日任务
    python run_trading_system.py --daily

    # 仅检测信号
    python run_trading_system.py --signal-only

    # 显示系统状态
    python run_trading_system.py --status

    # 初始化配置
    python run_trading_system.py --init
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from logger import SystemLogger
from data_quality_checker import DataQualityChecker


class TradingSystemRunner:
    """
    交易系统统一运行器

    协调所有模块的运行
    """

    def __init__(self):
        """初始化系统"""
        self.config = ConfigManager()
        self.logger = SystemLogger('trading_system')
        self.data_checker = DataQualityChecker()

        # 动态导入模块（避免启动时导入失败）
        self.modules = {}

    def _import_module(self, module_name: str):
        """动态导入模块"""
        if module_name in self.modules:
            return self.modules[module_name]

        try:
            if module_name == 'real_data_fetcher':
                from real_data_fetcher import RealDataFetcher
                self.modules[module_name] = RealDataFetcher
            elif module_name == 'signal_notifier':
                from signal_notifier import SignalNotifier
                self.modules[module_name] = SignalNotifier
            elif module_name == 'portfolio_management':
                from portfolio_management import PortfolioManager
                self.modules[module_name] = PortfolioManager
            else:
                raise ImportError(f"未知模块: {module_name}")

            return self.modules[module_name]
        except ImportError as e:
            self.logger.error(f"导入模块 {module_name} 失败: {e}")
            return None

    def initialize_system(self):
        """
        初始化系统配置

        首次运行时配置邮件、数据源等
        """
        print("\n" + "=" * 60)
        print("🚀 交易系统初始化向导")
        print("=" * 60)

        # 1. 验证配置文件
        print("\n📋 步骤 1/4: 验证系统配置...")
        if self.config.validate_config():
            print("配置验证通过")
        else:
            print("请修正配置文件后重试")
            return False

        # 2. 配置邮件
        print("\n📧 步骤 2/4: 配置邮件通知...")
        SignalNotifier = self._import_module('signal_notifier')
        if SignalNotifier:
            notifier = SignalNotifier()
            if not notifier.config:
                notifier.setup_email()
            else:
                print("邮件已配置")

        # 3. 测试数据源
        print("\n📊 步骤 3/4: 测试数据源...")
        self._test_data_source()

        # 4. 初始化组合
        print("\n💼 步骤 4/4: 初始化投资组合...")
        PortfolioManager = self._import_module('portfolio_management')
        if PortfolioManager:
            pm = PortfolioManager()
            account = pm.get_account_info()
            if account:
                print(f"账户已初始化，可用资金: ¥{account[1]:,.2f}")
            else:
                print("投资组合数据库已就绪")

        print("\n" + "=" * 60)
        print("✅ 系统初始化完成！")
        print("=" * 60)
        print("\n下一步:")
        print("  运行每日任务: python run_trading_system.py --daily")
        print("  查看系统状态: python run_trading_system.py --status")

        return True

    def _test_data_source(self):
        """测试数据源连接"""
        RealDataFetcher = self._import_module('real_data_fetcher')
        if not RealDataFetcher:
            print("无法导入数据获取模块")
            return False

        fetcher = RealDataFetcher()

        # 测试获取单个股票数据
        test_stock = self.config.get_stock_pool()[0] if self.config.get_stock_pool() else '600000'
        print(f"测试获取 {test_stock} 数据...")

        try:
            data = fetcher.fetch_single_stock(test_stock, days=5)
            if data is not None and len(data) > 0:
                print(f"✅ 数据源连接正常，获取到 {len(data)} 条记录")
                return True
            else:
                print("⚠️ 数据源返回空数据")
                return False
        except Exception as e:
            print(f"❌ 数据源测试失败: {e}")
            return False

    def run_daily_workflow(self):
        """
        运行每日工作流程

        完整流程:
        1. 更新市场数据
        2. 检查数据质量
        3. 检测交易信号
        4. 监控持仓风险
        5. 发送邮件报告
        """
        self.logger.log_system_start()
        start_time = time.time()

        print("\n" + "=" * 60)
        print(f"📈 每日交易系统运行 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        workflow_results = {
            'data_update': False,
            'quality_check': False,
            'signal_detection': False,
            'risk_monitor': False,
            'notification': False
        }

        # ========== 步骤 1: 更新市场数据 ==========
        print("\n⏳ [1/5] 更新市场数据...")
        market_data = self._update_market_data()
        if market_data is not None and len(market_data) > 0:
            print(f"✅ 数据更新完成，获取 {len(market_data.columns)} 只股票数据")
            workflow_results['data_update'] = True
            self.logger.log_data_update(
                self.config.get('data_source.default', 'yahoo'),
                len(market_data.columns),
                len(market_data)
            )
        else:
            print("❌ 数据更新失败")
            self.logger.error("数据更新失败")

        # ========== 步骤 2: 数据质量检查 ==========
        if workflow_results['data_update']:
            print("\n⏳ [2/5] 检查数据质量...")
            quality_result = self._check_data_quality(market_data)
            if quality_result:
                workflow_results['quality_check'] = True
                print("✅ 数据质量检查通过")
            else:
                print("⚠️ 数据质量存在问题，请检查日志")

        # ========== 步骤 3: 检测交易信号 ==========
        signals = None
        if workflow_results['data_update']:
            print("\n⏳ [3/5] 检测交易信号...")
            signals = self._detect_signals(market_data)
            if signals:
                buy_count = len(signals.get('buy_signals', []))
                sell_count = len(signals.get('sell_signals', []))
                watch_count = len(signals.get('watch_signals', []))

                print(f"✅ 信号检测完成: 买入 {buy_count}, 卖出 {sell_count}, 关注 {watch_count}")
                workflow_results['signal_detection'] = True
                self.logger.log_signal_detection(buy_count, sell_count, watch_count)
            else:
                print("⚠️ 信号检测失败或无信号")

        # ========== 步骤 4: 风险监控 ==========
        print("\n⏳ [4/5] 监控持仓风险...")
        risk_alerts = self._monitor_risks()
        if risk_alerts is not None:
            workflow_results['risk_monitor'] = True
            if risk_alerts:
                print(f"⚠️ 发现 {len(risk_alerts)} 个风险提醒")
                for alert in risk_alerts:
                    self.logger.log_risk_alert(
                        alert.get('type', 'unknown'),
                        alert.get('code', ''),
                        alert.get('profit_pct', 0),
                        alert.get('message', '')
                    )
            else:
                print("✅ 持仓风险正常")

        # ========== 步骤 5: 发送邮件通知 ==========
        print("\n⏳ [5/5] 发送邮件通知...")
        if self._send_notification(signals, risk_alerts):
            workflow_results['notification'] = True
            print("✅ 邮件发送成功")
        else:
            print("⚠️ 邮件发送失败，请检查配置")

        # ========== 总结 ==========
        elapsed_time = time.time() - start_time

        print("\n" + "=" * 60)
        print("📊 每日任务执行总结")
        print("=" * 60)

        success_count = sum(workflow_results.values())
        total_count = len(workflow_results)

        for task, success in workflow_results.items():
            status = "✅" if success else "❌"
            task_name = {
                'data_update': '数据更新',
                'quality_check': '质量检查',
                'signal_detection': '信号检测',
                'risk_monitor': '风险监控',
                'notification': '邮件通知'
            }.get(task, task)
            print(f"  {status} {task_name}")

        print(f"\n完成度: {success_count}/{total_count} ({100*success_count/total_count:.0f}%)")
        print(f"总耗时: {elapsed_time:.2f} 秒")
        print("=" * 60)

        self.logger.log_system_stop()

        return workflow_results

    def _update_market_data(self):
        """更新市场数据"""
        RealDataFetcher = self._import_module('real_data_fetcher')
        if not RealDataFetcher:
            return None

        try:
            fetcher = RealDataFetcher()
            stocks = self.config.get_stock_pool()
            days = self.config.get('data_source.history_days', 365)

            # 获取多只股票数据
            data = fetcher.fetch_multiple_stocks(stocks, days=days)

            return data
        except Exception as e:
            self.logger.log_exception(e, "更新市场数据")
            return None

    def _check_data_quality(self, data):
        """检查数据质量"""
        try:
            # 对每只股票检查质量
            all_passed = True

            for column in data.columns:
                stock_data = data[[column]].copy()
                stock_data.columns = ['close']

                quality = self.data_checker.check_data(stock_data)

                if quality['quality_score'] < 60:
                    all_passed = False
                    self.logger.log_data_quality_issue(
                        str(column),
                        'low_quality',
                        f"质量评分: {quality['quality_score']:.1f}"
                    )

            return all_passed
        except Exception as e:
            self.logger.log_exception(e, "数据质量检查")
            return False

    def _detect_signals(self, market_data):
        """检测交易信号"""
        SignalNotifier = self._import_module('signal_notifier')
        if not SignalNotifier:
            return None

        try:
            notifier = SignalNotifier()
            signals = notifier.detect_signals(market_data)

            execution_time = time.time() - time.time()  # 简化，实际应记录
            self.logger.log_strategy_result("综合策略", len(signals.get('buy_signals', [])), 0)

            return signals
        except Exception as e:
            self.logger.log_exception(e, "信号检测")
            return None

    def _monitor_risks(self):
        """监控持仓风险"""
        PortfolioManager = self._import_module('portfolio_management')
        if not PortfolioManager:
            return None

        try:
            pm = PortfolioManager()

            # 获取持仓
            positions = pm.get_positions()
            if not positions:
                return []

            # 检查风险
            alerts = []
            risk_params = self.config.get_risk_params()
            stop_loss = risk_params.get('stop_loss_threshold', -0.08)
            take_profit = risk_params.get('take_profit_threshold', 0.15)

            for pos in positions:
                code, shares, avg_cost, current_price, market_value, profit, profit_pct, last_update = pos

                # 检查止损
                if profit_pct <= stop_loss * 100:
                    alerts.append({
                        'type': 'stop_loss',
                        'code': code,
                        'profit_pct': profit_pct,
                        'message': f'触及止损线 {stop_loss*100:.1f}%，当前亏损 {profit_pct:.2f}%'
                    })

                # 检查止盈
                if profit_pct >= take_profit * 100:
                    alerts.append({
                        'type': 'take_profit',
                        'code': code,
                        'profit_pct': profit_pct,
                        'message': f'触及止盈线 {take_profit*100:.1f}%，当前盈利 {profit_pct:.2f}%'
                    })

            # 记录持仓状态
            account = pm.get_account_info()
            if account:
                total_value = account['total_value']
                cash = account['cash']
                pnl_pct = account['total_pnl_pct']
                self.logger.log_portfolio_status(total_value, cash, len(positions), pnl_pct)

            return alerts
        except Exception as e:
            self.logger.log_exception(e, "风险监控")
            return None

    def _send_notification(self, signals, risk_alerts):
        """发送通知邮件"""
        SignalNotifier = self._import_module('signal_notifier')
        if not SignalNotifier:
            return False

        try:
            notifier = SignalNotifier()

            if not notifier.config:
                self.logger.warning("邮件未配置，跳过发送")
                return False

            # 如果没有信号且配置不发送
            if not signals or (not signals.get('buy_signals') and not signals.get('watch_signals')):
                if not self.config.get('notification.send_on_no_signal', False):
                    self.logger.info("无交易信号，根据配置不发送邮件")
                    return True

            # 发送邮件
            success = notifier.send_signal_email(signals)

            if success:
                self.logger.log_email_sent(
                    notifier.config.get('recipient', ''),
                    '每日交易信号报告',
                    True
                )
            else:
                self.logger.log_email_sent(
                    notifier.config.get('recipient', ''),
                    '每日交易信号报告',
                    False
                )

            return success
        except Exception as e:
            self.logger.log_exception(e, "发送通知")
            return False

    def run_signal_only(self):
        """
        仅运行信号检测（不发送邮件）

        快速查看当前市场信号
        """
        print("\n" + "=" * 60)
        print("🔍 快速信号检测")
        print("=" * 60)

        # 获取数据
        print("⏳ 获取市场数据...")
        market_data = self._update_market_data()

        if market_data is None or len(market_data) == 0:
            print("❌ 无法获取市场数据")
            return

        # 检测信号
        print("⏳ 检测交易信号...")
        SignalNotifier = self._import_module('signal_notifier')
        if not SignalNotifier:
            print("❌ 无法导入信号检测模块")
            return

        notifier = SignalNotifier()
        signals = notifier.detect_signals(market_data)

        # 显示结果
        print("\n" + "=" * 60)
        print("📊 信号检测结果")
        print("=" * 60)

        # 买入信号
        buy_signals = signals.get('buy_signals', [])
        if buy_signals:
            print(f"\n🟢 买入信号 ({len(buy_signals)} 只):")
            for i, signal in enumerate(buy_signals[:10], 1):
                print(f"  {i}. {signal['code']} | 评分: {signal['score']:.1f} | "
                      f"策略数: {signal['strategies']}")
        else:
            print("\n🟢 买入信号: 无")

        # 关注信号
        watch_signals = signals.get('watch_signals', [])
        if watch_signals:
            print(f"\n🟡 关注信号 ({len(watch_signals)} 只):")
            for i, signal in enumerate(watch_signals[:5], 1):
                print(f"  {i}. {signal['code']} | 评分: {signal['score']:.1f}")
        else:
            print("\n🟡 关注信号: 无")

        # 卖出信号
        sell_signals = signals.get('sell_signals', [])
        if sell_signals:
            print(f"\n🔴 卖出信号 ({len(sell_signals)} 只):")
            for i, signal in enumerate(sell_signals[:5], 1):
                print(f"  {i}. {signal['code']} | 评分: {signal['score']:.1f}")

        print("\n" + "=" * 60)

    def show_system_status(self):
        """显示系统状态"""
        print("\n" + "=" * 60)
        print("📊 系统状态概览")
        print("=" * 60)

        # 1. 配置状态
        print("\n📋 配置状态:")
        print(f"  系统名称: {self.config.get('system.name')}")
        print(f"  版本: {self.config.get('system.version')}")
        print(f"  数据源: {self.config.get('data_source.default')}")
        print(f"  已启用策略: {', '.join(self.config.get_enabled_strategies())}")

        # 2. 股票池
        stocks = self.config.get_stock_pool()
        print(f"\n📈 股票池: {len(stocks)} 只股票")
        if stocks:
            print(f"  前5只: {', '.join(stocks[:5])}")

        # 3. 风险参数
        risk = self.config.get_risk_params()
        print(f"\n⚠️ 风险控制:")
        print(f"  止损线: {risk.get('stop_loss_threshold', 0)*100:.1f}%")
        print(f"  止盈线: {risk.get('take_profit_threshold', 0)*100:.1f}%")
        print(f"  单股最大仓位: {risk.get('max_single_position_pct', 0)*100:.1f}%")

        # 4. 邮件配置
        SignalNotifier = self._import_module('signal_notifier')
        if SignalNotifier:
            notifier = SignalNotifier()
            if notifier.config:
                print(f"\n📧 邮件通知: 已配置")
                print(f"  收件人: {notifier.config.get('recipient', '')}")
            else:
                print(f"\n📧 邮件通知: 未配置")

        # 5. 投资组合
        PortfolioManager = self._import_module('portfolio_management')
        if PortfolioManager:
            pm = PortfolioManager()
            account = pm.get_account_info()
            if account:
                print(f"\n💼 投资组合:")
                print(f"  总资产: ¥{account['total_value']:,.2f}")
                print(f"  可用现金: ¥{account['cash']:,.2f}")
                print(f"  持仓市值: ¥{account['positions_value']:,.2f}")
                print(f"  总盈亏: {account['total_pnl_pct']:+.2f}%")
            else:
                print(f"\n💼 投资组合: 未初始化")

        # 6. 日志目录
        log_dir = Path(__file__).parent / "logs"
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            total_size = sum(f.stat().st_size for f in log_files) / 1024 / 1024
            print(f"\n📁 日志文件: {len(log_files)} 个 ({total_size:.2f} MB)")

        print("\n" + "=" * 60)

    def run_interactive_menu(self):
        """交互式菜单"""
        while True:
            print("\n" + "=" * 60)
            print("📈 自动化交易系统 - 主菜单")
            print("=" * 60)
            print("1. 运行每日完整任务")
            print("2. 快速信号检测")
            print("3. 查看系统状态")
            print("4. 管理投资组合")
            print("5. 配置邮件通知")
            print("6. 查看/编辑配置")
            print("7. 初始化系统")
            print("0. 退出")
            print("=" * 60)

            choice = input("请选择 (0-7): ").strip()

            if choice == '1':
                self.run_daily_workflow()
            elif choice == '2':
                self.run_signal_only()
            elif choice == '3':
                self.show_system_status()
            elif choice == '4':
                PortfolioManager = self._import_module('portfolio_management')
                if PortfolioManager:
                    pm = PortfolioManager()
                    pm.interactive_menu()
            elif choice == '5':
                SignalNotifier = self._import_module('signal_notifier')
                if SignalNotifier:
                    notifier = SignalNotifier()
                    notifier.setup_email()
            elif choice == '6':
                self.config.print_config()
                if input("\n是否验证配置？(y/n): ").lower() == 'y':
                    self.config.validate_config()
            elif choice == '7':
                self.initialize_system()
            elif choice == '0':
                print("再见！")
                break
            else:
                print("无效选项")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='自动化交易系统统一启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --daily           运行每日完整任务
  %(prog)s --signal-only     仅检测交易信号
  %(prog)s --status          查看系统状态
  %(prog)s --init            初始化系统配置
  %(prog)s --menu            交互式菜单
        """
    )

    parser.add_argument('--daily', action='store_true', help='运行每日完整工作流')
    parser.add_argument('--signal-only', action='store_true', help='仅检测交易信号')
    parser.add_argument('--status', action='store_true', help='显示系统状态')
    parser.add_argument('--init', action='store_true', help='初始化系统配置')
    parser.add_argument('--menu', action='store_true', help='启动交互式菜单')

    args = parser.parse_args()

    runner = TradingSystemRunner()

    # 根据参数执行相应功能
    if args.daily:
        runner.run_daily_workflow()
    elif args.signal_only:
        runner.run_signal_only()
    elif args.status:
        runner.show_system_status()
    elif args.init:
        runner.initialize_system()
    elif args.menu:
        runner.run_interactive_menu()
    else:
        # 默认显示帮助或运行交互式菜单
        print("\n欢迎使用自动化交易系统！")
        print("\n快速开始:")
        print("  python run_trading_system.py --init     # 首次使用，初始化系统")
        print("  python run_trading_system.py --daily    # 运行每日任务")
        print("  python run_trading_system.py --menu     # 交互式菜单")
        print("\n或运行 'python run_trading_system.py --help' 查看所有选项")


if __name__ == '__main__':
    main()
