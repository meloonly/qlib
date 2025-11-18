#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多渠道告警系统

支持的告警渠道：
1. 邮件 (Email) - SMTP
2. 钉钉 (DingTalk) - Webhook
3. 企业微信 (WeCom) - Webhook
4. Telegram - Bot API
5. Slack - Webhook
6. 日志文件 - 本地记录

告警级别：
- INFO: 一般信息
- WARNING: 警告
- ERROR: 错误
- CRITICAL: 严重错误

使用方法:
    from alert_system import AlertSystem

    alert = AlertSystem(config_file='alert_config.yaml')

    # 发送告警
    alert.send('系统启动成功', level='INFO')
    alert.send('数据更新失败', level='ERROR', details={'code': '600000'})
    alert.send('策略异常', level='CRITICAL', channels=['email', 'dingtalk'])

配置文件 alert_config.yaml:
    channels:
      email:
        enabled: true
        smtp_server: smtp.gmail.com
        smtp_port: 587
        username: your@email.com
        password: your_password
        recipients: [alert@email.com]

      dingtalk:
        enabled: true
        webhook: https://oapi.dingtalk.com/robot/send?access_token=xxx
        secret: SEC...

      wecom:
        enabled: false
        webhook: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

      telegram:
        enabled: false
        bot_token: 123456:ABC-DEF...
        chat_id: -100123456789
"""

import smtplib
import requests
import json
import time
import hmac
import hashlib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import yaml


class AlertSystem:
    """多渠道告警系统"""

    # 告警级别
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    # 级别对应的emoji
    LEVEL_EMOJI = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨"
    }

    def __init__(self, config_file: str = None, config: dict = None):
        """
        初始化告警系统

        Args:
            config_file: 配置文件路径
            config: 配置字典（优先级高于config_file）
        """
        self.config = self._load_config(config_file, config)
        self.log_file = Path("logs/alerts.log")
        self.log_file.parent.mkdir(exist_ok=True)

        # 告警历史（用于防止重复告警）
        self.alert_history = []
        self.dedup_window = 300  # 5分钟内相同告警不重复发送

    def _load_config(self, config_file: str, config: dict) -> dict:
        """加载配置"""
        if config:
            return config

        if config_file and Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

        # 默认配置
        return {
            "channels": {
                "email": {"enabled": False},
                "dingtalk": {"enabled": False},
                "wecom": {"enabled": False},
                "telegram": {"enabled": False},
                "log": {"enabled": True}
            },
            "alert_levels": {
                "INFO": ["log"],
                "WARNING": ["log", "dingtalk"],
                "ERROR": ["log", "email", "dingtalk"],
                "CRITICAL": ["log", "email", "dingtalk", "telegram"]
            }
        }

    def send(self, message: str, level: str = "INFO",
             details: Dict = None, channels: List[str] = None) -> bool:
        """
        发送告警

        Args:
            message: 告警消息
            level: 告警级别 (INFO/WARNING/ERROR/CRITICAL)
            details: 详细信息（字典）
            channels: 指定发送渠道（不指定则根据级别自动选择）

        Returns:
            是否成功发送
        """
        # 防重复告警
        if self._is_duplicate(message, level):
            return True

        # 构造完整消息
        full_message = self._format_message(message, level, details)

        # 确定发送渠道
        if channels is None:
            channels = self.config.get("alert_levels", {}).get(level, ["log"])

        success = True

        # 发送到各个渠道
        for channel in channels:
            try:
                if channel == "email" and self._is_channel_enabled("email"):
                    self._send_email(full_message, level)
                elif channel == "dingtalk" and self._is_channel_enabled("dingtalk"):
                    self._send_dingtalk(full_message, level)
                elif channel == "wecom" and self._is_channel_enabled("wecom"):
                    self._send_wecom(full_message, level)
                elif channel == "telegram" and self._is_channel_enabled("telegram"):
                    self._send_telegram(full_message, level)
                elif channel == "log":
                    self._log_alert(full_message, level)
            except Exception as e:
                print(f"⚠️ {channel} 发送失败: {str(e)}")
                success = False

        # 记录历史
        self.alert_history.append({
            "message": message,
            "level": level,
            "time": time.time()
        })

        # 清理旧历史
        cutoff = time.time() - self.dedup_window
        self.alert_history = [h for h in self.alert_history if h["time"] > cutoff]

        return success

    def _is_duplicate(self, message: str, level: str) -> bool:
        """检查是否重复告警"""
        cutoff = time.time() - self.dedup_window
        for hist in self.alert_history:
            if hist["time"] > cutoff and hist["message"] == message and hist["level"] == level:
                return True
        return False

    def _is_channel_enabled(self, channel: str) -> bool:
        """检查渠道是否启用"""
        return self.config.get("channels", {}).get(channel, {}).get("enabled", False)

    def _format_message(self, message: str, level: str, details: Dict = None) -> str:
        """格式化告警消息"""
        emoji = self.LEVEL_EMOJI.get(level, "")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = [
            f"{emoji} [{level}] 交易系统告警",
            f"时间: {timestamp}",
            f"消息: {message}"
        ]

        if details:
            lines.append("\n详细信息:")
            for key, value in details.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _log_alert(self, message: str, level: str):
        """记录到日志文件"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] [{level}] {message}\n\n")

    def _send_email(self, message: str, level: str):
        """发送邮件告警"""
        config = self.config["channels"]["email"]

        msg = MIMEMultipart()
        msg['From'] = config['username']
        msg['To'] = ", ".join(config['recipients'])
        msg['Subject'] = f"[{level}] 交易系统告警"

        msg.attach(MIMEText(message, 'plain', 'utf-8'))

        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['username'], config['password'])
            server.send_message(msg)

        print(f"✅ 邮件已发送到 {config['recipients']}")

    def _send_dingtalk(self, message: str, level: str):
        """发送钉钉告警"""
        config = self.config["channels"]["dingtalk"]
        webhook = config['webhook']

        # 如果有签名
        if 'secret' in config:
            timestamp = str(int(time.time() * 1000))
            secret = config['secret']
            secret_enc = secret.encode('utf-8')
            string_to_sign = f'{timestamp}\n{secret}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = base64.b64encode(hmac_code).decode('utf-8')
            webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"

        data = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }

        response = requests.post(webhook, json=data)

        if response.json().get("errcode") == 0:
            print("✅ 钉钉消息已发送")
        else:
            raise Exception(f"钉钉发送失败: {response.text}")

    def _send_wecom(self, message: str, level: str):
        """发送企业微信告警"""
        config = self.config["channels"]["wecom"]
        webhook = config['webhook']

        data = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }

        response = requests.post(webhook, json=data)

        if response.json().get("errcode") == 0:
            print("✅ 企业微信消息已发送")
        else:
            raise Exception(f"企业微信发送失败: {response.text}")

    def _send_telegram(self, message: str, level: str):
        """发送Telegram告警"""
        config = self.config["channels"]["telegram"]
        bot_token = config['bot_token']
        chat_id = config['chat_id']

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(url, json=data)

        if response.json().get("ok"):
            print("✅ Telegram消息已发送")
        else:
            raise Exception(f"Telegram发送失败: {response.text}")

    def send_system_status(self, status: Dict):
        """发送系统状态报告"""
        if status.get("healthy", True):
            level = "INFO"
            message = "✅ 系统运行正常"
        else:
            level = "WARNING"
            message = "⚠️ 系统存在异常"

        details = {
            "CPU使用率": f"{status.get('cpu_percent', 0):.1f}%",
            "内存使用率": f"{status.get('memory_percent', 0):.1f}%",
            "磁盘使用率": f"{status.get('disk_percent', 0):.1f}%",
            "运行时长": status.get('uptime', 'unknown')
        }

        self.send(message, level=level, details=details)

    def send_trade_signal(self, code: str, action: str, price: float, reason: str):
        """发送交易信号告警"""
        message = f"📈 交易信号: {code} - {action}"
        details = {
            "股票代码": code,
            "操作": action,
            "价格": f"¥{price:.2f}",
            "原因": reason
        }
        self.send(message, level="WARNING", details=details)

    def send_risk_alert(self, risk_type: str, risk_value: float, threshold: float):
        """发送风险告警"""
        message = f"🚨 风险告警: {risk_type}"
        details = {
            "风险类型": risk_type,
            "当前值": f"{risk_value:.4f}",
            "阈值": f"{threshold:.4f}",
            "超出": f"{((risk_value / threshold - 1) * 100):.2f}%"
        }
        self.send(message, level="CRITICAL", details=details)

    def send_data_update_report(self, stats: Dict):
        """发送数据更新报告"""
        message = f"📊 数据更新完成"
        details = {
            "总数": stats.get('total', 0),
            "成功": stats.get('updated', 0) + stats.get('new', 0),
            "失败": stats.get('failed', 0),
            "跳过": stats.get('skipped', 0),
            "新增记录": stats.get('total_records', 0)
        }

        level = "INFO" if stats.get('failed', 0) == 0 else "WARNING"
        self.send(message, level=level, details=details)

    def send_error(self, error_type: str, error_msg: str, traceback_str: str = None):
        """发送错误告警"""
        message = f"❌ 系统错误: {error_type}"
        details = {
            "错误类型": error_type,
            "错误信息": error_msg[:200]
        }

        if traceback_str:
            details["堆栈跟踪"] = traceback_str[:500]

        self.send(message, level="ERROR", details=details)


class SystemMonitor:
    """系统监控器 - 配合告警系统使用"""

    def __init__(self, alert_system: AlertSystem):
        """
        初始化系统监控

        Args:
            alert_system: 告警系统实例
        """
        self.alert = alert_system
        self.start_time = time.time()

    def check_system_health(self) -> Dict:
        """检查系统健康状态"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            status = {
                "healthy": True,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "uptime": self._format_uptime()
            }

            # 检查阈值
            if cpu_percent > 80:
                status["healthy"] = False
                self.alert.send(
                    f"CPU使用率过高: {cpu_percent:.1f}%",
                    level="WARNING"
                )

            if memory.percent > 85:
                status["healthy"] = False
                self.alert.send(
                    f"内存使用率过高: {memory.percent:.1f}%",
                    level="WARNING"
                )

            if disk.percent > 90:
                status["healthy"] = False
                self.alert.send(
                    f"磁盘使用率过高: {disk.percent:.1f}%",
                    level="CRITICAL"
                )

            return status

        except ImportError:
            return {
                "healthy": True,
                "uptime": self._format_uptime(),
                "note": "psutil未安装，无法监控系统资源"
            }

    def _format_uptime(self) -> str:
        """格式化运行时长"""
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        return f"{hours}小时{minutes}分钟"

    def monitor_loop(self, interval: int = 3600):
        """监控循环（每小时检查一次）"""
        print(f"🔍 启动系统监控 (间隔: {interval}秒)")

        while True:
            try:
                status = self.check_system_health()
                self.alert.send_system_status(status)
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n⏹️ 监控已停止")
                break
            except Exception as e:
                self.alert.send_error("SystemMonitor", str(e))
                time.sleep(interval)


# 创建默认配置文件
def create_default_config():
    """创建默认告警配置文件"""
    config = {
        "channels": {
            "email": {
                "enabled": False,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "your@email.com",
                "password": "your_password",
                "recipients": ["alert@email.com"]
            },
            "dingtalk": {
                "enabled": False,
                "webhook": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
                "secret": "SECxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            },
            "wecom": {
                "enabled": False,
                "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
            },
            "telegram": {
                "enabled": False,
                "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "chat_id": "-100123456789"
            },
            "log": {
                "enabled": True
            }
        },
        "alert_levels": {
            "INFO": ["log"],
            "WARNING": ["log", "dingtalk"],
            "ERROR": ["log", "email", "dingtalk"],
            "CRITICAL": ["log", "email", "dingtalk", "telegram"]
        }
    }

    config_file = Path("alert_config.yaml")
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"✅ 已创建默认配置文件: {config_file}")
    print("请编辑配置文件并填入真实的告警渠道信息")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='告警系统')
    parser.add_argument('--create-config', action='store_true',
                       help='创建默认配置文件')
    parser.add_argument('--test', action='store_true',
                       help='测试告警发送')
    parser.add_argument('--monitor', action='store_true',
                       help='启动系统监控')

    args = parser.parse_args()

    if args.create_config:
        create_default_config()

    elif args.test:
        # 测试告警
        alert = AlertSystem()

        alert.send("这是一条测试消息", level="INFO")
        alert.send("这是一条警告消息", level="WARNING", details={"stock": "600000"})
        alert.send("这是一条错误消息", level="ERROR")

        print("\n✅ 测试完成，请查看 logs/alerts.log")

    elif args.monitor:
        # 启动监控
        alert = AlertSystem()
        monitor = SystemMonitor(alert)
        monitor.monitor_loop(interval=3600)

    else:
        parser.print_help()
