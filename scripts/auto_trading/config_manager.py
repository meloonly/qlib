#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置管理中心

集中管理所有系统参数，避免硬编码。
支持YAML格式配置文件，便于阅读和修改。

使用方法:
    from config_manager import ConfigManager

    config = ConfigManager()
    risk_params = config.get_risk_params()
    strategy_params = config.get_strategy_params()
"""

import yaml
from pathlib import Path
from typing import Any, Dict
import os


class ConfigManager:
    """
    配置管理器

    统一管理所有系统参数
    """

    def __init__(self, config_path: str = None):
        """
        初始化配置管理器

        参数:
            config_path: 配置文件路径，默认为当前目录下的system_config.yaml
        """
        if config_path is None:
            config_path = str(Path(__file__).parent / "system_config.yaml")

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """加载配置文件"""
        if Path(self.config_path).exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print(f"✅ 配置文件已加载: {self.config_path}")
            return config
        else:
            print(f"⚠️ 配置文件不存在，创建默认配置: {self.config_path}")
            config = self._create_default_config()
            self._save_config(config)
            return config

    def _save_config(self, config: dict = None):
        """保存配置文件"""
        if config is None:
            config = self.config

        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"✅ 配置已保存: {self.config_path}")

    def _create_default_config(self) -> dict:
        """创建默认配置"""
        return {
            # 系统基本设置
            'system': {
                'name': '自动化交易系统',
                'version': '1.0.0',
                'author': 'Auto Trading System',
                'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
                'log_dir': 'logs',
                'report_dir': 'reports',
                'data_dir': 'data',
            },

            # 数据源配置
            'data_source': {
                'default': 'yahoo',  # yahoo, tushare
                'yahoo': {
                    'delay_between_requests': 0.5,  # 秒
                    'max_retries': 3,
                },
                'tushare': {
                    'token': '',  # 在这里填写您的token
                    'delay_between_requests': 0.3,
                },
                'history_days': 365,  # 默认获取多少天历史数据
            },

            # 风险控制参数
            'risk_control': {
                'stop_loss_threshold': -0.08,  # 止损线 -8%
                'take_profit_threshold': 0.15,  # 止盈线 15%
                'max_single_position_pct': 0.20,  # 单股最大仓位 20%
                'min_cash_ratio': 0.05,  # 最低现金比例 5%
                'max_daily_trades': 10,  # 每日最大交易次数
                'max_drawdown_alert': -0.10,  # 最大回撤警告 -10%
            },

            # 策略参数
            'strategies': {
                'dual_ma': {
                    'enabled': True,
                    'short_window': 5,
                    'long_window': 20,
                    'weight': 0.25,  # 策略权重
                },
                'momentum': {
                    'enabled': True,
                    'lookback_period': 20,
                    'holding_period': 5,
                    'weight': 0.25,
                },
                'mean_reversion': {
                    'enabled': True,
                    'window': 20,
                    'std_multiplier': 2.0,
                    'rsi_period': 14,
                    'weight': 0.25,
                },
                'alpha101': {
                    'enabled': True,
                    'rebalance_freq': 5,
                    'weight': 0.25,
                },
            },

            # 信号检测参数
            'signal_detection': {
                'buy_score_threshold': 75,  # 买入评分阈值
                'sell_score_threshold': 40,  # 卖出评分阈值
                'watch_score_threshold': 65,  # 关注评分阈值
                'min_strategy_consensus': 2,  # 最少策略共识数
                'topk_stocks': 30,  # 选股数量
            },

            # 回测参数
            'backtest': {
                'initial_capital': 1000000,  # 初始资金
                'transaction_cost_buy': 0.0003,  # 买入手续费 0.03%
                'transaction_cost_sell': 0.0013,  # 卖出手续费 0.13%（含印花税）
                'slippage': 0.001,  # 滑点 0.1%
            },

            # 邮件通知配置
            'notification': {
                'enabled': True,
                'send_time': '16:00',  # 发送时间
                'send_on_no_signal': False,  # 无信号时是否发送
                'max_buy_signals_in_email': 10,  # 邮件中最多显示的买入信号数
                'max_alerts_in_email': 5,  # 邮件中最多显示的提醒数
            },

            # 数据质量检查
            'data_quality': {
                'min_data_days': 60,  # 最少数据天数
                'max_missing_pct': 0.05,  # 最大缺失比例 5%
                'max_price_change_pct': 0.20,  # 单日最大涨跌幅（超过视为异常）
                'min_volume': 100000,  # 最小成交量
            },

            # 股票池配置
            'stock_pool': {
                'default_stocks': [
                    '600000', '600036', '601318', '600519', '000858',
                    '000001', '002594', '600030', '601166', '601398'
                ],
                'exclude_st': True,  # 排除ST股票
                'exclude_new_stocks_days': 60,  # 排除上市不足60天的新股
            },
        }

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持嵌套键）

        参数:
            key_path: 配置键路径，如 'risk_control.stop_loss_threshold'
            default: 默认值

        返回:
            配置值
        """
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any, save: bool = True):
        """
        设置配置值

        参数:
            key_path: 配置键路径
            value: 值
            save: 是否立即保存到文件
        """
        keys = key_path.split('.')
        config = self.config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value

        if save:
            self._save_config()

    def get_risk_params(self) -> dict:
        """获取风险控制参数"""
        return self.config.get('risk_control', {})

    def get_strategy_params(self, strategy_name: str = None) -> dict:
        """
        获取策略参数

        参数:
            strategy_name: 策略名称，如果为None则返回所有策略参数
        """
        strategies = self.config.get('strategies', {})
        if strategy_name:
            return strategies.get(strategy_name, {})
        return strategies

    def get_enabled_strategies(self) -> list:
        """获取已启用的策略列表"""
        strategies = self.config.get('strategies', {})
        enabled = []
        for name, params in strategies.items():
            if params.get('enabled', False):
                enabled.append(name)
        return enabled

    def get_signal_params(self) -> dict:
        """获取信号检测参数"""
        return self.config.get('signal_detection', {})

    def get_backtest_params(self) -> dict:
        """获取回测参数"""
        return self.config.get('backtest', {})

    def get_notification_params(self) -> dict:
        """获取通知参数"""
        return self.config.get('notification', {})

    def get_data_quality_params(self) -> dict:
        """获取数据质量检查参数"""
        return self.config.get('data_quality', {})

    def get_stock_pool(self) -> list:
        """获取默认股票池"""
        return self.config.get('stock_pool', {}).get('default_stocks', [])

    def update_stock_pool(self, stocks: list):
        """更新股票池"""
        self.set('stock_pool.default_stocks', stocks)

    def print_config(self):
        """打印当前配置"""
        print("\n" + "=" * 60)
        print("📋 当前系统配置")
        print("=" * 60)
        print(yaml.dump(self.config, default_flow_style=False, allow_unicode=True))
        print("=" * 60)

    def reset_to_default(self):
        """重置为默认配置"""
        if input("⚠️ 确认重置为默认配置？这将覆盖当前配置 (y/n): ").lower() == 'y':
            self.config = self._create_default_config()
            self._save_config()
            print("✅ 已重置为默认配置")

    def validate_config(self) -> bool:
        """
        验证配置的合法性

        返回:
            是否合法
        """
        errors = []

        # 检查风险参数
        risk = self.get_risk_params()
        if risk.get('stop_loss_threshold', 0) > 0:
            errors.append("止损阈值应为负数")
        if risk.get('take_profit_threshold', 0) < 0:
            errors.append("止盈阈值应为正数")
        if not 0 < risk.get('max_single_position_pct', 0) <= 1:
            errors.append("单股最大仓位应在0-100%之间")

        # 检查策略权重
        strategies = self.get_strategy_params()
        total_weight = sum(s.get('weight', 0) for s in strategies.values() if s.get('enabled'))
        if abs(total_weight - 1.0) > 0.01:
            errors.append(f"已启用策略的权重之和应为1，当前为{total_weight:.2f}")

        # 检查信号参数
        signal = self.get_signal_params()
        if signal.get('buy_score_threshold', 0) <= signal.get('watch_score_threshold', 0):
            errors.append("买入阈值应大于关注阈值")

        if errors:
            print("❌ 配置验证失败:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("✅ 配置验证通过")
            return True


def main():
    """测试配置管理器"""
    config = ConfigManager()

    print("\n--- 测试配置读取 ---")
    print(f"止损阈值: {config.get('risk_control.stop_loss_threshold')}")
    print(f"买入评分阈值: {config.get('signal_detection.buy_score_threshold')}")
    print(f"已启用策略: {config.get_enabled_strategies()}")
    print(f"股票池: {config.get_stock_pool()}")

    print("\n--- 验证配置 ---")
    config.validate_config()

    print("\n✅ 配置管理器测试完成")


if __name__ == '__main__':
    main()
