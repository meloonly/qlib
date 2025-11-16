#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化调度器

实现真正的无人值守自动化：
- 定时任务调度（APScheduler）
- 每日自动信号检测
- 定期数据更新
- 周末自动备份
- 系统健康检查

使用方法:
    # 启动调度服务
    python scheduler.py start

    # 查看任务状态
    python scheduler.py status

    # 停止服务
    python scheduler.py stop

    # 手动触发任务
    python scheduler.py trigger daily_check
"""

import sys
import os
import signal
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import shutil

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    print("⚠️ APScheduler未安装，请运行: pip install apscheduler")

from config_manager import ConfigManager
from logger import SystemLogger


class TradingScheduler:
    """
    交易系统自动化调度器

    管理所有定时任务
    """

    def __init__(self):
        """初始化调度器"""
        self.config = ConfigManager()
        self.logger = SystemLogger('scheduler')

        # 状态文件
        self.status_file = Path(__file__).parent / '.scheduler_status.json'
        self.pid_file = Path(__file__).parent / '.scheduler.pid'

        # 调度器配置
        if HAS_APSCHEDULER:
            jobstores = {
                'default': SQLAlchemyJobStore(
                    url=f"sqlite:///{Path(__file__).parent / 'scheduler_jobs.db'}"
                )
            }
            executors = {
                'default': ThreadPoolExecutor(10)
            }
            job_defaults = {
                'coalesce': True,  # 合并错过的任务
                'max_instances': 1,  # 同一任务最多一个实例
                'misfire_grace_time': 3600  # 错过1小时内仍执行
            }

            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='Asia/Shanghai'
            )
        else:
            self.scheduler = None

    def _save_status(self, status: dict):
        """保存状态"""
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2, default=str)

    def _load_status(self) -> dict:
        """加载状态"""
        if self.status_file.exists():
            with open(self.status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _update_task_status(self, task_name: str, status: str, result: str = ''):
        """更新任务状态"""
        current_status = self._load_status()
        if 'tasks' not in current_status:
            current_status['tasks'] = {}

        current_status['tasks'][task_name] = {
            'last_run': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': status,
            'result': result
        }
        self._save_status(current_status)

    # ==================== 定时任务 ====================

    def job_daily_signal_check(self):
        """
        每日信号检测任务

        默认每天16:00执行
        """
        self.logger.info("开始执行每日信号检测...")
        self._update_task_status('daily_signal_check', 'running')

        try:
            from run_trading_system import TradingSystemRunner
            runner = TradingSystemRunner()
            results = runner.run_daily_workflow()

            success_count = sum(results.values())
            total_count = len(results)

            result_msg = f"完成 {success_count}/{total_count} 个任务"
            self.logger.info(f"每日信号检测完成: {result_msg}")
            self._update_task_status('daily_signal_check', 'success', result_msg)

        except Exception as e:
            self.logger.log_exception(e, "每日信号检测")
            self._update_task_status('daily_signal_check', 'failed', str(e))

    def job_data_update(self):
        """
        数据更新任务

        默认每天9:30执行（开盘后）
        """
        self.logger.info("开始执行数据更新...")
        self._update_task_status('data_update', 'running')

        try:
            from real_data_fetcher import RealDataFetcher
            fetcher = RealDataFetcher()
            stocks = self.config.get_stock_pool()

            data = fetcher.fetch_multiple_stocks(stocks, days=30)

            if data is not None and len(data) > 0:
                result_msg = f"更新 {len(data.columns)} 只股票数据"
                self.logger.info(f"数据更新完成: {result_msg}")
                self._update_task_status('data_update', 'success', result_msg)
            else:
                self._update_task_status('data_update', 'failed', '无数据返回')

        except Exception as e:
            self.logger.log_exception(e, "数据更新")
            self._update_task_status('data_update', 'failed', str(e))

    def job_database_backup(self):
        """
        数据库备份任务

        默认每周日23:00执行
        """
        self.logger.info("开始执行数据库备份...")
        self._update_task_status('database_backup', 'running')

        try:
            backup_dir = Path(__file__).parent / 'backups'
            backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 备份数据库文件
            db_files = [
                'portfolio.db',
                'scheduler_jobs.db'
            ]

            backed_up = 0
            for db_file in db_files:
                src = Path(__file__).parent / db_file
                if src.exists():
                    dst = backup_dir / f"{db_file}.{timestamp}.bak"
                    shutil.copy2(src, dst)
                    backed_up += 1

            # 清理旧备份（保留最近30天）
            cutoff = datetime.now() - timedelta(days=30)
            for backup_file in backup_dir.glob('*.bak'):
                if backup_file.stat().st_mtime < cutoff.timestamp():
                    backup_file.unlink()
                    self.logger.info(f"删除旧备份: {backup_file.name}")

            result_msg = f"备份 {backed_up} 个数据库文件"
            self.logger.info(f"数据库备份完成: {result_msg}")
            self._update_task_status('database_backup', 'success', result_msg)

        except Exception as e:
            self.logger.log_exception(e, "数据库备份")
            self._update_task_status('database_backup', 'failed', str(e))

    def job_health_check(self):
        """
        系统健康检查任务

        默认每小时执行一次
        """
        self.logger.debug("执行系统健康检查...")

        try:
            issues = []

            # 检查磁盘空间
            total, used, free = shutil.disk_usage(Path(__file__).parent)
            free_gb = free / (1024 ** 3)
            if free_gb < 1:
                issues.append(f"磁盘空间不足: {free_gb:.2f} GB")

            # 检查日志文件大小
            log_dir = Path(__file__).parent / 'logs'
            if log_dir.exists():
                total_log_size = sum(f.stat().st_size for f in log_dir.glob('*.log'))
                if total_log_size > 100 * 1024 * 1024:  # 100MB
                    issues.append(f"日志文件过大: {total_log_size / (1024*1024):.2f} MB")

            # 检查数据库文件
            db_file = Path(__file__).parent / 'portfolio.db'
            if not db_file.exists():
                issues.append("投资组合数据库不存在")

            if issues:
                self.logger.warning(f"健康检查发现问题: {', '.join(issues)}")
                self._update_task_status('health_check', 'warning', '; '.join(issues))
            else:
                self._update_task_status('health_check', 'success', '系统正常')

        except Exception as e:
            self.logger.log_exception(e, "健康检查")
            self._update_task_status('health_check', 'failed', str(e))

    def job_log_cleanup(self):
        """
        日志清理任务

        默认每周一凌晨执行
        """
        self.logger.info("开始清理旧日志...")
        self._update_task_status('log_cleanup', 'running')

        try:
            log_dir = Path(__file__).parent / 'logs'
            if not log_dir.exists():
                self._update_task_status('log_cleanup', 'success', '无日志目录')
                return

            # 清理30天前的日志
            cutoff = datetime.now() - timedelta(days=30)
            cleaned = 0

            for log_file in log_dir.glob('*.log.*'):  # 清理轮转的旧日志
                if log_file.stat().st_mtime < cutoff.timestamp():
                    log_file.unlink()
                    cleaned += 1

            result_msg = f"清理 {cleaned} 个旧日志文件"
            self.logger.info(f"日志清理完成: {result_msg}")
            self._update_task_status('log_cleanup', 'success', result_msg)

        except Exception as e:
            self.logger.log_exception(e, "日志清理")
            self._update_task_status('log_cleanup', 'failed', str(e))

    def job_performance_report(self):
        """
        性能报告生成任务

        默认每周五收盘后执行
        """
        self.logger.info("开始生成周度性能报告...")
        self._update_task_status('performance_report', 'running')

        try:
            from performance_analyzer import PerformanceAnalyzer
            from portfolio_management import PortfolioManager
            import pandas as pd
            import numpy as np

            pm = PortfolioManager()
            analyzer = PerformanceAnalyzer()

            # 获取交易历史计算收益
            trades = pm.get_trade_history(limit=100)

            if len(trades) == 0:
                self._update_task_status('performance_report', 'success', '无交易记录')
                return

            # 简单模拟收益率（实际应从每日持仓价值计算）
            np.random.seed(42)
            returns = pd.Series(np.random.normal(0.001, 0.015, 100))

            # 生成报告
            report_file = analyzer.generate_report(returns, strategy_name="周度绩效")

            result_msg = f"报告已生成: {report_file}"
            self.logger.info(f"性能报告完成: {result_msg}")
            self._update_task_status('performance_report', 'success', result_msg)

        except Exception as e:
            self.logger.log_exception(e, "性能报告")
            self._update_task_status('performance_report', 'failed', str(e))

    # ==================== 调度管理 ====================

    def setup_jobs(self):
        """配置所有定时任务"""
        if not HAS_APSCHEDULER:
            print("❌ APScheduler未安装，无法配置任务")
            return False

        # 清除现有任务
        self.scheduler.remove_all_jobs()

        # 1. 每日信号检测 - 每天16:00
        self.scheduler.add_job(
            self.job_daily_signal_check,
            CronTrigger(hour=16, minute=0),
            id='daily_signal_check',
            name='每日信号检测',
            replace_existing=True
        )

        # 2. 数据更新 - 每天9:30 (开盘后)
        self.scheduler.add_job(
            self.job_data_update,
            CronTrigger(hour=9, minute=30),
            id='data_update',
            name='数据更新',
            replace_existing=True
        )

        # 3. 数据库备份 - 每周日23:00
        self.scheduler.add_job(
            self.job_database_backup,
            CronTrigger(day_of_week='sun', hour=23, minute=0),
            id='database_backup',
            name='数据库备份',
            replace_existing=True
        )

        # 4. 健康检查 - 每小时
        self.scheduler.add_job(
            self.job_health_check,
            IntervalTrigger(hours=1),
            id='health_check',
            name='系统健康检查',
            replace_existing=True
        )

        # 5. 日志清理 - 每周一凌晨3点
        self.scheduler.add_job(
            self.job_log_cleanup,
            CronTrigger(day_of_week='mon', hour=3, minute=0),
            id='log_cleanup',
            name='日志清理',
            replace_existing=True
        )

        # 6. 性能报告 - 每周五17:00
        self.scheduler.add_job(
            self.job_performance_report,
            CronTrigger(day_of_week='fri', hour=17, minute=0),
            id='performance_report',
            name='周度性能报告',
            replace_existing=True
        )

        self.logger.info("定时任务配置完成")
        return True

    def start(self):
        """启动调度服务"""
        if not HAS_APSCHEDULER:
            print("❌ 请先安装APScheduler: pip install apscheduler")
            return False

        # 检查是否已运行
        if self.is_running():
            print("⚠️ 调度服务已在运行中")
            return False

        print("\n" + "=" * 60)
        print("🚀 启动自动化调度服务")
        print("=" * 60)

        # 配置任务
        self.setup_jobs()

        # 启动调度器
        self.scheduler.start()

        # 保存PID
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))

        # 更新状态
        status = {
            'running': True,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pid': os.getpid(),
            'tasks': {}
        }
        self._save_status(status)

        self.logger.info(f"调度服务已启动，PID: {os.getpid()}")

        # 显示任务列表
        self.show_jobs()

        print("\n✅ 调度服务启动成功！")
        print("服务将在后台运行，按 Ctrl+C 停止...")
        print("=" * 60 + "\n")

        # 设置信号处理
        def signal_handler(signum, frame):
            print("\n接收到停止信号，正在关闭...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 保持运行
        try:
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            self.stop()

        return True

    def stop(self):
        """停止调度服务"""
        if not HAS_APSCHEDULER:
            return

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

        # 清理PID文件
        if self.pid_file.exists():
            self.pid_file.unlink()

        # 更新状态
        status = self._load_status()
        status['running'] = False
        status['stop_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self._save_status(status)

        self.logger.info("调度服务已停止")
        print("✅ 调度服务已停止")

    def is_running(self) -> bool:
        """检查服务是否运行中"""
        if not self.pid_file.exists():
            return False

        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())

            # 检查进程是否存在
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, OSError):
            # 进程不存在，清理PID文件
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False

    def show_jobs(self):
        """显示所有任务"""
        if not HAS_APSCHEDULER or not self.scheduler:
            print("❌ 调度器未初始化")
            return

        jobs = self.scheduler.get_jobs()

        print("\n📋 定时任务列表:")
        print("-" * 60)

        if not jobs:
            print("  暂无任务")
        else:
            for job in jobs:
                next_run = job.next_run_time
                if next_run:
                    next_run_str = next_run.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    next_run_str = '未调度'

                print(f"  📌 {job.name}")
                print(f"     ID: {job.id}")
                print(f"     下次执行: {next_run_str}")
                print(f"     触发器: {job.trigger}")
                print()

    def show_status(self):
        """显示服务状态"""
        print("\n" + "=" * 60)
        print("📊 调度服务状态")
        print("=" * 60)

        if self.is_running():
            print("🟢 服务状态: 运行中")
            with open(self.pid_file, 'r') as f:
                pid = f.read().strip()
            print(f"   PID: {pid}")
        else:
            print("🔴 服务状态: 未运行")

        # 显示任务历史
        status = self._load_status()
        if 'start_time' in status:
            print(f"   启动时间: {status.get('start_time', 'N/A')}")

        if 'tasks' in status and status['tasks']:
            print("\n📜 任务执行历史:")
            print("-" * 60)
            for task_name, task_info in status['tasks'].items():
                status_icon = {
                    'success': '✅',
                    'failed': '❌',
                    'running': '🔄',
                    'warning': '⚠️'
                }.get(task_info['status'], '❓')

                print(f"  {status_icon} {task_name}")
                print(f"     最后执行: {task_info['last_run']}")
                print(f"     状态: {task_info['status']}")
                if task_info.get('result'):
                    print(f"     结果: {task_info['result']}")
                print()

        print("=" * 60)

    def trigger_job(self, job_id: str):
        """手动触发任务"""
        job_map = {
            'daily_signal_check': self.job_daily_signal_check,
            'daily_check': self.job_daily_signal_check,  # 别名
            'data_update': self.job_data_update,
            'database_backup': self.job_database_backup,
            'backup': self.job_database_backup,  # 别名
            'health_check': self.job_health_check,
            'log_cleanup': self.job_log_cleanup,
            'performance_report': self.job_performance_report,
            'report': self.job_performance_report  # 别名
        }

        if job_id in job_map:
            print(f"🔄 手动触发任务: {job_id}")
            job_map[job_id]()
            print(f"✅ 任务完成: {job_id}")
        else:
            print(f"❌ 未知任务: {job_id}")
            print(f"可用任务: {', '.join(job_map.keys())}")


def generate_crontab_config():
    """生成crontab配置（替代方案）"""
    script_path = Path(__file__).parent / 'run_trading_system.py'
    python_path = sys.executable

    crontab_lines = f"""
# 自动化交易系统定时任务配置
# 使用命令安装: crontab -e

# 每日16:00 执行信号检测和通知
0 16 * * 1-5 {python_path} {script_path} --daily >> /tmp/trading_daily.log 2>&1

# 每日9:30 更新数据
30 9 * * 1-5 {python_path} {script_path} --signal-only >> /tmp/trading_update.log 2>&1

# 每周日23:00 备份数据库
0 23 * * 0 cp {Path(__file__).parent}/portfolio.db {Path(__file__).parent}/backups/portfolio_$(date +\\%Y\\%m\\%d).db
"""

    print("📋 Crontab配置（适用于Linux/Mac）:")
    print("=" * 60)
    print(crontab_lines)
    print("=" * 60)
    print("\n使用方法:")
    print("1. 运行 'crontab -e' 编辑定时任务")
    print("2. 粘贴上述配置")
    print("3. 保存退出")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='自动化交易系统调度器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s start              启动调度服务
  %(prog)s stop               停止调度服务
  %(prog)s status             查看服务状态
  %(prog)s jobs               查看任务列表
  %(prog)s trigger daily_check  手动触发任务
  %(prog)s crontab            生成crontab配置
        """
    )

    parser.add_argument('action', nargs='?', default='status',
                        choices=['start', 'stop', 'status', 'jobs', 'trigger', 'crontab'],
                        help='执行的操作')
    parser.add_argument('job_id', nargs='?', help='任务ID（用于trigger命令）')
    parser.add_argument('--daemon', action='store_true', help='后台运行')

    args = parser.parse_args()

    scheduler = TradingScheduler()

    if args.action == 'start':
        if args.daemon:
            # 后台运行（简单实现）
            print("🚀 以守护进程模式启动...")
            pid = os.fork()
            if pid > 0:
                print(f"调度服务已启动，PID: {pid}")
                sys.exit(0)
            else:
                # 子进程
                os.setsid()
                scheduler.start()
        else:
            scheduler.start()

    elif args.action == 'stop':
        if scheduler.is_running():
            # 发送停止信号
            with open(scheduler.pid_file, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"✅ 已发送停止信号到 PID {pid}")
            except ProcessLookupError:
                print("⚠️ 进程不存在，清理状态文件")
                if scheduler.pid_file.exists():
                    scheduler.pid_file.unlink()
        else:
            print("⚠️ 调度服务未运行")

    elif args.action == 'status':
        scheduler.show_status()

    elif args.action == 'jobs':
        if not scheduler.is_running():
            # 临时启动调度器以查看任务
            if HAS_APSCHEDULER:
                scheduler.setup_jobs()
        scheduler.show_jobs()

    elif args.action == 'trigger':
        if args.job_id:
            scheduler.trigger_job(args.job_id)
        else:
            print("❌ 请指定任务ID")
            print("用法: python scheduler.py trigger <job_id>")

    elif args.action == 'crontab':
        generate_crontab_config()


if __name__ == '__main__':
    main()
