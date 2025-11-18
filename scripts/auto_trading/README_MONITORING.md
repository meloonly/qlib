# 数据维护和告警系统使用指南

## 概述

本系统新增了两大核心功能模块，让自动化交易系统真正实现无人值守：

1. **数据维护模块** - 确保数据持续新鲜、完整、准确
2. **多渠道告警系统** - 实时监控系统状态，异常及时通知

---

## 一、数据维护模块

### 功能特性

#### 1. 增量数据更新
- **智能增量**: 只下载缺失的日期数据，避免重复下载
- **断点续传**: 自动从上次更新的日期继续
- **节省带宽**: 相比全量更新节省90%+时间和流量

```python
from data_maintenance import DataMaintenance

dm = DataMaintenance()

# 增量更新指定股票
stocks = ['600000', '000001', '600036']
stats = dm.incremental_update(stocks, source='akshare')

# 输出统计
# {
#   'total': 3,
#   'new': 1,      # 首次下载
#   'updated': 2,  # 增量更新
#   'failed': 0,
#   'skipped': 0,
#   'total_records': 150
# }
```

#### 2. 数据完整性检查
自动检测5类数据问题：
- ✅ 日期连续性（交易日缺失）
- ✅ 重复数据（同一日期多条记录）
- ✅ 成交量异常（长期为0）
- ✅ 价格异常（单日涨跌幅>50%）
- ✅ 数据过时（超过7天未更新）

```python
# 检查数据完整性
report = dm.check_data_integrity(stocks)

print(f"总检查: {report['total_stocks']} 只股票")
print(f"发现问题: {len(report['issues'])} 个")
print(f"数据过时: {report['summary']['outdated']} 只")
```

#### 3. 自动修复
- 删除重复日期记录
- 填充价格缺失值（前值填充）
- 修正零成交量（平均值填充）

```python
# 自动修复数据问题
stats = dm.fix_data_issues(stocks)

print(f"处理文件: {stats['processed']}")
print(f"删除重复: {stats['fixed_duplicates']}")
print(f"修复零值: {stats['fixed_zeros']}")
```

#### 4. 历史数据归档
- 压缩3年前的历史数据（.csv.gz格式）
- 节省磁盘空间80%+
- 需要时可解压恢复

```python
# 归档1095天(3年)前的数据
stats = dm.archive_old_data(days=1095)

print(f"归档股票: {stats['processed']}")
print(f"归档记录: {stats['archived_records']}")
print(f"节省空间: {stats['saved_space']/1024/1024:.2f} MB")
```

#### 5. 数据质量报告
```python
# 生成完整的数据质量报告
report_text = dm.generate_report()
print(report_text)
```

---

## 二、多渠道告警系统

### 支持的告警渠道

| 渠道 | 说明 | 优先级 |
|-----|------|--------|
| **日志文件** | 本地logs/alerts.log | ⭐⭐⭐ 必备 |
| **邮件** | SMTP邮件通知 | ⭐⭐⭐ 推荐 |
| **钉钉** | 企业钉钉机器人 | ⭐⭐⭐ 推荐 |
| **企业微信** | 企业微信机器人 | ⭐⭐ 可选 |
| **Telegram** | Telegram Bot | ⭐⭐ 可选 |

### 告警级别

| 级别 | 图标 | 触发场景 | 默认渠道 |
|------|-----|----------|----------|
| **INFO** | ℹ️ | 正常信息 | 日志 |
| **WARNING** | ⚠️ | 警告（需关注） | 日志+钉钉 |
| **ERROR** | ❌ | 错误（需处理） | 日志+邮件+钉钉 |
| **CRITICAL** | 🚨 | 严重错误（立即处理） | 全部渠道 |

### 快速开始

#### 1. 配置告警渠道

编辑 `alert_config.yaml`:

```yaml
channels:
  # 邮件配置（推荐）
  email:
    enabled: true
    smtp_server: smtp.gmail.com
    smtp_port: 587
    username: your@email.com
    password: your_app_password  # Gmail需要使用应用专用密码
    recipients:
      - alert@email.com

  # 钉钉配置（推荐）
  dingtalk:
    enabled: true
    webhook: https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN
    secret: SEC...  # 加签密钥

  # 企业微信（可选）
  wecom:
    enabled: false
    webhook: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY

  # Telegram（可选）
  telegram:
    enabled: false
    bot_token: 123456:ABC-DEF...
    chat_id: -100123456789

# 告警级别配置
alert_levels:
  INFO: [log]
  WARNING: [log, dingtalk]
  ERROR: [log, email, dingtalk]
  CRITICAL: [log, email, dingtalk, telegram]
```

#### 2. 使用告警系统

```python
from alert_system import AlertSystem

# 初始化（自动加载alert_config.yaml）
alert = AlertSystem(config_file='alert_config.yaml')

# 发送告警
alert.send('系统启动成功', level='INFO')

alert.send(
    '数据更新失败',
    level='ERROR',
    details={'code': '600000', 'error': 'Network timeout'}
)

# 专用告警方法
alert.send_trade_signal(
    code='600000',
    action='BUY',
    price=10.50,
    reason='双均线金叉'
)

alert.send_risk_alert(
    risk_type='VaR',
    risk_value=0.08,
    threshold=0.05
)
```

#### 3. 系统监控

```python
from alert_system import SystemMonitor

monitor = SystemMonitor(alert)

# 检查系统健康
status = monitor.check_system_health()
# 自动发送告警（CPU/内存/磁盘超阈值）

# 启动监控循环（每小时检查）
monitor.monitor_loop(interval=3600)
```

### 获取告警渠道配置

#### 钉钉机器人

1. 打开钉钉群 → 群设置 → 智能群助手
2. 添加机器人 → 自定义
3. 安全设置选择"加签"
4. 复制Webhook地址和密钥到配置文件

#### 企业微信机器人

1. 企业微信群 → 群设置 → 群机器人
2. 添加机器人
3. 复制Webhook地址到配置文件

#### Telegram Bot

1. 在Telegram搜索 @BotFather
2. 发送 /newbot 创建机器人
3. 获取bot_token
4. 将机器人加入群组，获取chat_id

#### Gmail邮件

1. 开启两步验证
2. 生成应用专用密码
3. 使用应用密码而非账号密码

---

## 三、自动化调度集成

系统已将数据维护和告警功能集成到调度器中，实现全自动运行。

### 8个自动化任务

| 任务 | 执行时间 | 功能 | 告警 |
|------|----------|------|------|
| **数据更新** | 每天 09:30 | 增量更新股票数据 | ✅ |
| **每日信号检测** | 每天 16:00 | 生成交易信号 | ✅ |
| **系统健康检查** | 每小时 | 监控CPU/内存/磁盘 | ✅ |
| **日志清理** | 每周一 03:00 | 清理30天前日志 | ❌ |
| **数据完整性检查** | 每周三 00:00 | 检查数据质量 | ✅ |
| **数据自动修复** | 每周三 01:00 | 修复数据问题 | ✅ |
| **性能报告** | 每周五 17:00 | 生成周度报告 | ❌ |
| **数据库备份** | 每周日 23:00 | 备份数据库 | ❌ |

### 启动调度服务

```bash
# 启动调度器（自动运行所有任务）
python scheduler.py start

# 查看任务状态
python scheduler.py status

# 停止服务
python scheduler.py stop

# 手动触发任务
python scheduler.py trigger data_update
python scheduler.py trigger data_integrity_check
```

### Docker环境运行

```bash
# Docker Compose启动
docker-compose up -d

# 查看日志
docker-compose logs -f trading-system

# 进入容器检查
docker-compose exec trading-system python scheduler.py status
```

---

## 四、监控和日志

### 日志文件

| 文件 | 内容 |
|------|------|
| `logs/alerts.log` | 所有告警记录 |
| `logs/scheduler.log` | 调度器运行日志 |
| `logs/trading_system.log` | 系统主日志 |
| `data/data_metadata.json` | 数据更新元数据 |

### 查看实时告警

```bash
# 实时查看告警日志
tail -f logs/alerts.log

# 查看最近50条告警
tail -50 logs/alerts.log

# 搜索ERROR级别告警
grep "ERROR" logs/alerts.log
```

### 数据维护状态

```bash
# 查看数据元数据
cat data/data_metadata.json | jq .

# 查看数据更新历史
cat data/data_metadata.json | jq '.stocks'

# 查看最近问题
cat data/data_metadata.json | jq '.issues[-5:]'
```

---

## 五、最佳实践

### 1. 告警配置建议

**生产环境**：
- ✅ 启用邮件（ERROR及以上）
- ✅ 启用钉钉/企业微信（WARNING及以上）
- ✅ 日志始终启用

**开发环境**：
- ✅ 仅启用日志
- ❌ 关闭外部通知避免干扰

### 2. 数据维护策略

**每日**：
- 增量更新（09:30自动执行）
- 系统健康检查（每小时）

**每周**：
- 数据完整性检查（周三）
- 数据自动修复（周三）
- 数据库备份（周日）

**每月**：
- 手动执行：`dm.archive_old_data(days=1095)`
- 检查磁盘空间使用

### 3. 性能优化

```python
# 大批量更新时调整并发
dm = DataMaintenance()

# 分批更新（每批50只）
stocks = config.get_stock_pool()  # 假设200只
for i in range(0, len(stocks), 50):
    batch = stocks[i:i+50]
    dm.incremental_update(batch)
    time.sleep(60)  # 间隔1分钟
```

### 4. 错误处理

```python
from alert_system import AlertSystem

alert = AlertSystem()

try:
    # 你的交易逻辑
    run_trading_strategy()
except Exception as e:
    # 自动发送错误告警
    alert.send_error(
        error_type='StrategyError',
        error_msg=str(e),
        traceback_str=traceback.format_exc()
    )
```

---

## 六、故障排除

### 问题1：告警未发送

**检查**：
1. 查看 `logs/alerts.log` 是否有记录
2. 确认渠道配置正确且`enabled: true`
3. 检查网络连接（钉钉/企业微信/Telegram需要网络）

**解决**：
```bash
# 测试告警系统
python alert_system.py --test

# 查看日志
tail -f logs/alerts.log
```

### 问题2：数据更新失败

**检查**：
1. 网络连接（AKShare需要访问国内数据源）
2. 数据源是否可用
3. 磁盘空间是否充足

**解决**：
```bash
# 手动测试数据获取
python akshare_fetcher.py --check

# 查看错误日志
tail -50 logs/trading_system.log | grep ERROR
```

### 问题3：调度器未运行

**检查**：
```bash
# 检查调度器状态
python scheduler.py status

# 检查进程
ps aux | grep scheduler

# 查看PID文件
cat .scheduler.pid
```

**解决**：
```bash
# 停止旧进程
python scheduler.py stop

# 重新启动
python scheduler.py start
```

---

## 七、API参考

### DataMaintenance类

```python
dm = DataMaintenance(
    data_dir="./data",
    cache_dir="./data/akshare_cache"
)

# 增量更新
stats = dm.incremental_update(codes, source='akshare')

# 完整性检查
report = dm.check_data_integrity(codes)

# 自动修复
stats = dm.fix_data_issues(codes)

# 归档旧数据
stats = dm.archive_old_data(days=1095)

# 生成报告
report_text = dm.generate_report()
```

### AlertSystem类

```python
alert = AlertSystem(config_file='alert_config.yaml')

# 基础告警
alert.send(message, level='INFO', details={}, channels=[])

# 专用方法
alert.send_system_status(status)
alert.send_trade_signal(code, action, price, reason)
alert.send_risk_alert(risk_type, risk_value, threshold)
alert.send_data_update_report(stats)
alert.send_error(error_type, error_msg, traceback_str)
```

### SystemMonitor类

```python
monitor = SystemMonitor(alert_system)

# 健康检查
status = monitor.check_system_health()

# 监控循环
monitor.monitor_loop(interval=3600)
```

---

## 八、更新日志

**v1.0.0** (2025-11-17)
- ✅ 新增数据维护模块（700行代码）
- ✅ 新增多渠道告警系统（650行代码）
- ✅ 调度器集成增强（新增2个自动化任务）
- ✅ 总计新增代码1350+行

**主要特性**：
- 增量数据更新，节省90%时间
- 自动数据质量检查和修复
- 5渠道告警（邮件/钉钉/企业微信/Telegram/日志）
- 4级告警等级（INFO/WARNING/ERROR/CRITICAL）
- 防重复告警机制
- 系统资源监控
- 8个全自动化任务

---

## 支持

如有问题，请查看：
1. 日志文件：`logs/alerts.log` 和 `logs/trading_system.log`
2. 配置文件：`alert_config.yaml` 和 `system_config.yaml`
3. 元数据文件：`data/data_metadata.json`

祝交易顺利！📈
