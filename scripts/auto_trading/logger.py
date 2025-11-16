#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志系统

记录所有操作、错误和重要事件。
支持同时输出到控制台和文件。

使用方法:
    from logger import get_logger

    logger = get_logger('module_name')
    logger.info("操作成功")
    logger.warning("警告信息")
    logger.error("错误信息")
"""

import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime
import sys


def get_logger(name: str = 'auto_trading', log_dir: str = None,
               level: str = 'INFO', max_bytes: int = 10*1024*1024,
               backup_count: int = 5) -> logging.Logger:
    """
    获取日志记录器

    参数:
        name: 日志器名称
        log_dir: 日志目录
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: 单个日志文件最大字节数（默认10MB）
        backup_count: 保留的日志文件数量

    返回:
        Logger对象
    """
    if log_dir is None:
        log_dir = str(Path(__file__).parent / "logs")

    # 创建日志目录
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # 创建logger
    logger = logging.getLogger(name)

    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger

    # 设置日志级别
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    logger.setLevel(level_map.get(level.upper(), logging.INFO))

    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（按大小轮转）
    log_file = Path(log_dir) / f"{name}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 错误日志单独记录
    error_file = Path(log_dir) / f"{name}_error.log"
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # 交易日志单独记录
    trade_file = Path(log_dir) / f"{name}_trades.log"
    trade_handler = RotatingFileHandler(
        trade_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    trade_handler.setLevel(logging.INFO)
    trade_handler.setFormatter(formatter)

    # 创建交易专用logger
    trade_logger = logging.getLogger(f"{name}.trades")
    if not trade_logger.handlers:
        trade_logger.addHandler(trade_handler)
        trade_logger.setLevel(logging.INFO)

    return logger


def get_trade_logger(name: str = 'auto_trading') -> logging.Logger:
    """获取交易专用日志器"""
    return logging.getLogger(f"{name}.trades")


class SystemLogger:
    """
    系统日志管理器

    提供统一的日志接口，记录各类事件
    """

    def __init__(self, name: str = 'auto_trading'):
        self.logger = get_logger(name)
        self.trade_logger = get_trade_logger(name)

    def info(self, message: str):
        """记录信息"""
        self.logger.info(message)

    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(message)

    def error(self, message: str):
        """记录错误"""
        self.logger.error(message)

    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)

    def critical(self, message: str):
        """记录严重错误"""
        self.logger.critical(message)

    # ==================== 业务日志 ====================

    def log_system_start(self):
        """记录系统启动"""
        self.logger.info("=" * 60)
        self.logger.info("系统启动")
        self.logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)

    def log_system_stop(self):
        """记录系统停止"""
        self.logger.info("=" * 60)
        self.logger.info("系统停止")
        self.logger.info(f"停止时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 60)

    def log_data_update(self, source: str, stocks_count: int, records_count: int):
        """记录数据更新"""
        self.logger.info(f"数据更新 | 数据源: {source} | 股票数: {stocks_count} | 记录数: {records_count}")

    def log_signal_detection(self, buy_count: int, sell_count: int, watch_count: int):
        """记录信号检测"""
        self.logger.info(f"信号检测 | 买入: {buy_count} | 卖出: {sell_count} | 关注: {watch_count}")

    def log_trade(self, action: str, code: str, shares: int, price: float, reason: str = ''):
        """
        记录交易

        参数:
            action: 'buy' 或 'sell'
            code: 股票代码
            shares: 股数
            price: 价格
            reason: 交易原因
        """
        action_text = "买入" if action == 'buy' else "卖出"
        amount = shares * price
        message = f"交易执行 | {action_text} | {code} | {shares}股 | ¥{price:.2f} | 金额¥{amount:,.2f}"
        if reason:
            message += f" | 原因: {reason}"

        self.trade_logger.info(message)
        self.logger.info(message)

    def log_risk_alert(self, alert_type: str, code: str, profit_pct: float, message: str):
        """
        记录风险提醒

        参数:
            alert_type: 'stop_loss', 'take_profit', 'position_limit'
            code: 股票代码
            profit_pct: 盈亏百分比
            message: 提醒消息
        """
        self.logger.warning(f"风险提醒 | 类型: {alert_type} | {code} | 盈亏: {profit_pct:+.2f}% | {message}")

    def log_email_sent(self, recipient: str, subject: str, success: bool):
        """记录邮件发送"""
        if success:
            self.logger.info(f"邮件发送成功 | 收件人: {recipient} | 主题: {subject}")
        else:
            self.logger.error(f"邮件发送失败 | 收件人: {recipient} | 主题: {subject}")

    def log_data_quality_issue(self, code: str, issue_type: str, details: str):
        """记录数据质量问题"""
        self.logger.warning(f"数据质量问题 | {code} | 类型: {issue_type} | {details}")

    def log_strategy_result(self, strategy_name: str, signals_count: int, execution_time: float):
        """记录策略执行结果"""
        self.logger.info(f"策略执行 | {strategy_name} | 信号数: {signals_count} | 耗时: {execution_time:.2f}秒")

    def log_portfolio_status(self, total_value: float, cash: float, positions_count: int, pnl_pct: float):
        """记录持仓状态"""
        self.logger.info(
            f"持仓状态 | 总资产: ¥{total_value:,.2f} | 现金: ¥{cash:,.2f} | "
            f"持仓数: {positions_count} | 总盈亏: {pnl_pct:+.2f}%"
        )

    def log_exception(self, exception: Exception, context: str = ''):
        """记录异常"""
        import traceback
        error_msg = f"异常发生 | {context} | {type(exception).__name__}: {str(exception)}"
        self.logger.error(error_msg)
        self.logger.debug(traceback.format_exc())


def main():
    """测试日志系统"""
    print("测试日志系统...")

    # 创建系统日志器
    sys_logger = SystemLogger('test_trading')

    # 测试各种日志
    sys_logger.log_system_start()

    sys_logger.info("这是一条普通信息")
    sys_logger.warning("这是一条警告信息")
    sys_logger.error("这是一条错误信息")

    sys_logger.log_data_update('yahoo', 30, 12000)
    sys_logger.log_signal_detection(5, 2, 3)
    sys_logger.log_trade('buy', 'SH600000', 1000, 10.50, '策略信号')
    sys_logger.log_trade('sell', 'SH600036', 500, 35.80, '止盈')
    sys_logger.log_risk_alert('take_profit', 'SH600519', 18.5, '建议减仓')
    sys_logger.log_portfolio_status(1050000, 350000, 5, 5.0)
    sys_logger.log_email_sent('test@qq.com', '交易信号报告', True)

    try:
        raise ValueError("测试异常")
    except Exception as e:
        sys_logger.log_exception(e, "测试模块")

    sys_logger.log_system_stop()

    print("\n✅ 日志系统测试完成")
    print(f"📁 日志文件位置: {Path(__file__).parent / 'logs'}")


if __name__ == '__main__':
    main()
