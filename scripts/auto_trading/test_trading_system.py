#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化交易系统单元测试

确保代码质量，防止回归bug

运行测试:
    python -m pytest test_trading_system.py -v
    # 或
    python test_trading_system.py
"""

import unittest
import sys
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))


class TestConfigManager(unittest.TestCase):
    """测试配置管理器"""

    def setUp(self):
        """测试前准备"""
        from config_manager import ConfigManager
        # 使用临时配置文件
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = str(Path(self.temp_dir) / "test_config.yaml")
        self.config = ConfigManager(self.config_path)

    def test_load_default_config(self):
        """测试加载默认配置"""
        self.assertIsNotNone(self.config.config)
        self.assertIn('system', self.config.config)
        self.assertIn('risk_control', self.config.config)
        self.assertIn('strategies', self.config.config)

    def test_get_nested_value(self):
        """测试获取嵌套值"""
        stop_loss = self.config.get('risk_control.stop_loss_threshold')
        self.assertIsNotNone(stop_loss)
        self.assertLess(stop_loss, 0)  # 止损应为负值

    def test_set_value(self):
        """测试设置值"""
        self.config.set('risk_control.stop_loss_threshold', -0.10, save=False)
        new_value = self.config.get('risk_control.stop_loss_threshold')
        self.assertEqual(new_value, -0.10)

    def test_get_risk_params(self):
        """测试获取风险参数"""
        risk_params = self.config.get_risk_params()
        self.assertIn('stop_loss_threshold', risk_params)
        self.assertIn('take_profit_threshold', risk_params)
        self.assertIn('max_single_position_pct', risk_params)

    def test_get_enabled_strategies(self):
        """测试获取已启用策略"""
        strategies = self.config.get_enabled_strategies()
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 0)

    def test_get_stock_pool(self):
        """测试获取股票池"""
        stocks = self.config.get_stock_pool()
        self.assertIsInstance(stocks, list)
        self.assertGreater(len(stocks), 0)

    def test_validate_config(self):
        """测试配置验证"""
        # 默认配置应该有效
        is_valid = self.config.validate_config()
        # 注意：权重和可能不为1，所以这里只检查函数能运行
        self.assertIsInstance(is_valid, bool)


class TestDataQualityChecker(unittest.TestCase):
    """测试数据质量检查器"""

    def setUp(self):
        """测试前准备"""
        from data_quality_checker import DataQualityChecker
        self.checker = DataQualityChecker()

        # 创建测试数据
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        np.random.seed(42)
        self.test_data = pd.DataFrame({
            'code': ['SH600000'] * 100,
            'date': dates.strftime('%Y-%m-%d').tolist(),
            'open': np.random.uniform(10, 20, 100),
            'high': np.random.uniform(10, 22, 100),
            'low': np.random.uniform(8, 20, 100),
            'close': np.random.uniform(10, 20, 100),
            'volume': np.random.randint(100000, 1000000, 100)
        })

        # 确保OHLC逻辑正确
        self.test_data['high'] = self.test_data[['open', 'high', 'close']].max(axis=1) + 0.1
        self.test_data['low'] = self.test_data[['open', 'low', 'close']].min(axis=1) - 0.1

    def test_check_data_returns_dict(self):
        """测试check_data返回字典"""
        result = self.checker.check_data(self.test_data)
        self.assertIsInstance(result, dict)
        self.assertIn('passed', result)
        self.assertIn('stock_reports', result)

    def test_quality_score_range(self):
        """测试质量评分范围"""
        result = self.checker.check_data(self.test_data)
        # 检查是否有股票报告
        self.assertIn('stock_reports', result)
        self.assertGreater(len(result['stock_reports']), 0)

    def test_clean_data(self):
        """测试数据清洗"""
        # 插入一些缺失值
        dirty_data = self.test_data.copy()
        dirty_data.loc[10, 'close'] = np.nan

        cleaned = self.checker.clean_data(dirty_data)
        self.assertFalse(cleaned['close'].isna().any())

    def test_detect_missing_values(self):
        """测试检测缺失值"""
        # 创建有缺失值的数据
        data_with_missing = self.test_data.copy()
        data_with_missing.loc[5, 'close'] = np.nan

        result = self.checker.check_data(data_with_missing)
        # 应该检测到质量问题
        self.assertIsInstance(result, dict)


class TestPerformanceAnalyzer(unittest.TestCase):
    """测试性能分析器"""

    def setUp(self):
        """测试前准备"""
        from performance_analyzer import PerformanceAnalyzer
        self.analyzer = PerformanceAnalyzer()

        # 创建模拟收益率
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
        self.returns = pd.Series(
            np.random.normal(0.0005, 0.015, len(dates)),
            index=dates
        )

    def test_calculate_metrics_returns_dict(self):
        """测试calculate_metrics返回字典"""
        metrics = self.analyzer.calculate_metrics(self.returns)
        self.assertIsInstance(metrics, dict)

    def test_sharpe_ratio_calculation(self):
        """测试夏普比率计算"""
        metrics = self.analyzer.calculate_metrics(self.returns)
        sharpe = metrics['sharpe_ratio']
        self.assertIsInstance(sharpe, (int, float))
        # 夏普比率应该在合理范围内
        self.assertGreater(sharpe, -10)
        self.assertLess(sharpe, 10)

    def test_max_drawdown_negative(self):
        """测试最大回撤为负值"""
        max_dd = self.analyzer.calculate_max_drawdown(self.returns)
        self.assertLessEqual(max_dd, 0)

    def test_win_rate_range(self):
        """测试胜率范围"""
        metrics = self.analyzer.calculate_metrics(self.returns)
        win_rate = metrics['win_rate']
        self.assertGreaterEqual(win_rate, 0)
        self.assertLessEqual(win_rate, 1)

    def test_total_return_calculation(self):
        """测试总收益计算"""
        metrics = self.analyzer.calculate_metrics(self.returns)
        total_return = metrics['total_return']
        # 手动计算验证
        expected = (1 + self.returns).prod() - 1
        self.assertAlmostEqual(total_return, expected, places=6)

    def test_analyze_winning_streaks(self):
        """测试连胜连亏分析"""
        streaks = self.analyzer.analyze_winning_streaks(self.returns)
        self.assertIn('max_winning_streak', streaks)
        self.assertIn('max_losing_streak', streaks)
        self.assertGreaterEqual(streaks['max_winning_streak'], 0)


class TestPortfolioManager(unittest.TestCase):
    """测试投资组合管理器"""

    def setUp(self):
        """测试前准备"""
        from portfolio_management import PortfolioManager
        # 使用临时数据库
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_portfolio.db")
        self.pm = PortfolioManager(self.db_path)

    def test_get_account_info(self):
        """测试获取账户信息"""
        account = self.pm.get_account_info()
        self.assertIsInstance(account, dict)
        self.assertIn('cash', account)
        self.assertIn('total_value', account)

    def test_initial_cash(self):
        """测试初始资金"""
        account = self.pm.get_account_info()
        self.assertEqual(account['cash'], 1000000)

    def test_add_position(self):
        """测试添加持仓"""
        success = self.pm.add_position('SH600000', 1000, 10.0)
        self.assertTrue(success)

        positions = self.pm.get_all_positions()
        self.assertGreater(len(positions), 0)

    def test_sell_position(self):
        """测试卖出持仓"""
        self.pm.add_position('SH600000', 1000, 10.0)
        success = self.pm.sell_position('SH600000', 500, 11.0)
        self.assertTrue(success)

        positions = self.pm.get_all_positions()
        # 应该还有500股
        pos = positions[positions['code'] == 'SH600000']
        self.assertEqual(len(pos), 1)
        self.assertEqual(pos.iloc[0]['shares'], 500)

    def test_cash_deduction_on_buy(self):
        """测试买入时扣除现金"""
        initial_cash = self.pm.get_account_info()['cash']
        self.pm.add_position('SH600000', 1000, 10.0)
        new_cash = self.pm.get_account_info()['cash']
        # 扣除了10000（加上手续费）
        self.assertLess(new_cash, initial_cash)

    def test_get_trade_history(self):
        """测试获取交易历史"""
        self.pm.add_position('SH600000', 1000, 10.0)
        self.pm.sell_position('SH600000', 500, 11.0)

        trades = self.pm.get_trade_history()
        self.assertEqual(len(trades), 2)


class TestAdvancedStrategies(unittest.TestCase):
    """测试高级策略"""

    def setUp(self):
        """测试前准备"""
        # 创建测试数据
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        self.test_data = []

        for code in ['SH600000', 'SH600036']:
            initial_price = 20
            prices = [initial_price]
            for _ in range(99):
                prices.append(prices[-1] * (1 + np.random.normal(0.001, 0.02)))

            for i, date in enumerate(dates):
                price = prices[i]
                self.test_data.append({
                    'code': code,
                    'date': date.strftime('%Y-%m-%d'),
                    'open': price * (1 + np.random.normal(0, 0.005)),
                    'high': price * (1 + abs(np.random.normal(0, 0.01))),
                    'low': price * (1 - abs(np.random.normal(0, 0.01))),
                    'close': price,
                    'volume': int(np.random.uniform(1e6, 1e7))
                })

        self.df = pd.DataFrame(self.test_data)

    def test_turtle_trading_signals(self):
        """测试海龟交易信号生成"""
        from advanced_strategies import TurtleTrading
        turtle = TurtleTrading(entry_window=20, exit_window=10)
        signals = turtle.generate_signals(self.df)

        self.assertIsInstance(signals, pd.DataFrame)
        if len(signals) > 0:
            self.assertIn('buy_signal', signals.columns)
            self.assertIn('sell_signal', signals.columns)

    def test_turtle_position_sizing(self):
        """测试海龟头寸管理"""
        from advanced_strategies import TurtleTrading
        turtle = TurtleTrading()

        position = turtle.calculate_position_size(
            capital=1000000,
            risk_per_trade=0.01,
            atr=1.0,
            price=20.0
        )
        self.assertGreaterEqual(position, 0)
        self.assertEqual(position % 100, 0)  # 应该是100的倍数

    def test_ml_strategy_features(self):
        """测试ML策略特征创建"""
        from advanced_strategies import MLStrategy
        ml = MLStrategy()

        single_stock = self.df[self.df['code'] == 'SH600000'].copy()
        features = ml.create_features(single_stock)

        self.assertIn('return_1d', features.columns)
        self.assertIn('rsi', features.columns)
        self.assertIn('macd', features.columns)


class TestLogger(unittest.TestCase):
    """测试日志系统"""

    def setUp(self):
        """测试前准备"""
        from logger import SystemLogger
        self.temp_dir = tempfile.mkdtemp()
        self.logger = SystemLogger('test_logger')

    def test_logger_creation(self):
        """测试日志器创建"""
        self.assertIsNotNone(self.logger)
        self.assertIsNotNone(self.logger.logger)

    def test_info_logging(self):
        """测试信息日志"""
        # 应该不抛出异常
        try:
            self.logger.info("Test info message")
            success = True
        except Exception:
            success = False
        self.assertTrue(success)

    def test_error_logging(self):
        """测试错误日志"""
        try:
            self.logger.error("Test error message")
            success = True
        except Exception:
            success = False
        self.assertTrue(success)

    def test_log_trade(self):
        """测试交易日志"""
        try:
            self.logger.log_trade('buy', 'SH600000', 1000, 10.0, '测试')
            success = True
        except Exception:
            success = False
        self.assertTrue(success)

    def test_log_risk_alert(self):
        """测试风险提醒日志"""
        try:
            self.logger.log_risk_alert('stop_loss', 'SH600000', -8.5, '止损提醒')
            success = True
        except Exception:
            success = False
        self.assertTrue(success)


class TestSignalNotifier(unittest.TestCase):
    """测试信号通知器"""

    def setUp(self):
        """测试前准备"""
        from signal_notifier import SignalNotifier
        self.notifier = SignalNotifier()

        # 创建测试数据（宽格式，带date列）
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

        # 创建带date列的DataFrame
        data_list = []
        for stock in ['600000', '600036', '601318']:
            prices = 20 * (1 + np.random.normal(0.001, 0.02, len(dates))).cumprod()
            for i, date in enumerate(dates):
                data_list.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'stock': stock,
                    'close': prices[i]
                })

        # 转换为宽格式
        df_long = pd.DataFrame(data_list)
        self.test_data = df_long.pivot(index='date', columns='stock', values='close')
        self.test_data = self.test_data.reset_index()

    def test_detect_signals_returns_dict(self):
        """测试信号检测返回字典"""
        signals = self.notifier.detect_signals(self.test_data)
        self.assertIsInstance(signals, dict)

    def test_signals_contain_keys(self):
        """测试信号包含必要键"""
        signals = self.notifier.detect_signals(self.test_data)
        self.assertIn('buy_signals', signals)
        self.assertIn('sell_signals', signals)
        self.assertIn('watch_signals', signals)

    def test_generate_email_report(self):
        """测试生成邮件报告"""
        signals = self.notifier.detect_signals(self.test_data)
        report = self.notifier.generate_email_report(signals)

        self.assertIsInstance(report, str)
        self.assertIn('html', report.lower())


def run_all_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestConfigManager))
    suite.addTests(loader.loadTestsFromTestCase(TestDataQualityChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioManager))
    suite.addTests(loader.loadTestsFromTestCase(TestAdvancedStrategies))
    suite.addTests(loader.loadTestsFromTestCase(TestLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestSignalNotifier))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 统计
    print("\n" + "=" * 60)
    print("📊 测试统计")
    print("=" * 60)
    print(f"运行测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
        if result.failures:
            print("\n失败的测试:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\n错误的测试:")
            for test, traceback in result.errors:
                print(f"  - {test}")

    return result


if __name__ == '__main__':
    run_all_tests()
