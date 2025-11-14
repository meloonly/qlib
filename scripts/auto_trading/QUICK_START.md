# 快速开始指南 - 股票分析工具

## 🎯 三种使用方式

### 1️⃣ 快速分析股票（无需持仓数据）

**适用场景**: 想快速了解几只股票的技术指标和投资建议

```bash
# 分析多只股票
python quick_analysis.py SH600000 SH600036 SH510300

# 生成HTML报告
python quick_analysis.py SH600000 SH600036 --report
```

**输出内容**:
- 基本信息（价格、涨跌幅、成交量）
- 技术指标（MA、RSI、MACD、布林带）
- 风险指标（收益率、夏普比率、最大回撤）
- 交易建议（买入/卖出/持有）
- 综合评分（0-100分）
- 股票对比分析

---

### 2️⃣ 监控持仓 + 每日交易提示（推荐）

**适用场景**: 已有持仓，每天想知道该买入、卖出还是持有

#### 步骤1: 创建持仓文件

创建 `my_portfolio.csv` 文件：

```csv
code,shares,cost_price
SH600000,1000,10.50
SH600036,2000,12.30
SH510300,5000,3.80
```

- `code`: 股票代码
- `shares`: 持有股数
- `cost_price`: 买入成本价

#### 步骤2: 运行每日监控

```bash
# 分析持仓 + 生成交易建议
python portfolio_monitor.py --portfolio my_portfolio.csv

# 生成HTML日报
python portfolio_monitor.py --portfolio my_portfolio.csv --daily-report

# 同时推荐新股票
python portfolio_monitor.py --portfolio my_portfolio.csv --daily-report --recommend SH600519,SH601318
```

**输出内容**:
- 持仓总体情况（总成本、总市值、总盈亏）
- 每只股票的盈亏分析
- **每日交易建议**:
  - 🔴 建议卖出（止盈/止损）
  - 🟢 建议加仓（低位机会）
  - ⚪ 持有观望
- 🌟 新投资机会推荐

---

### 3️⃣ 完整自动化交易系统

**适用场景**: 需要完整的量化交易解决方案，包括数据更新、模型训练、组合优化

```bash
# 运行完整流程
python main_controller.py --config config.yaml

# 配置定时任务（每天自动运行）
bash setup_cron.sh
```

---

## 📊 决策逻辑说明

### 卖出信号（止盈/止损）

| 条件 | 说明 | 优先级 |
|------|------|--------|
| 盈利>20% 且 RSI>70 | 止盈（超买） | 高 |
| 亏损>10% 且 评分<50 | 止损（基本面变差） | 高 |

### 加仓信号

| 条件 | 说明 | 优先级 |
|------|------|--------|
| 小幅亏损(-5%) + RSI<30 + 评分≥60 | 超卖反弹机会 | 中 |
| 盈利 + 评分≥60 + RSI<70 | 追涨机会 | 低 |

### 持有观望

其他情况默认持有观望

---

## 📝 常见问题

### Q1: 如何手动添加持仓？

```bash
python portfolio_monitor.py --add SH600000:1000:10.5,SH600036:2000:12.3
```

格式：`股票代码:股数:成本价`

### Q2: 如何分析ETF？

ETF和股票使用相同的命令：

```bash
python quick_analysis.py SH510300 SH510500 SH512000
```

### Q3: 数据从哪里来？

当前版本使用**模拟数据**进行演示。

要使用真实数据，需要：
1. 安装 `yahooquery` 或 `tushare`
2. 修改 `quick_analysis.py` 中的 `fetch_stock_data()` 方法
3. 或使用完整版 `main_controller.py`（包含数据下载功能）

### Q4: 如何配置定时任务？

```bash
# 每天下午4点（收盘后）自动运行
# 在 crontab 中添加：
0 16 * * 1-5 python /path/to/portfolio_monitor.py --portfolio my_portfolio.csv --daily-report
```

或使用提供的脚本：

```bash
bash setup_cron.sh
```

---

## 🎨 报告示例

### 每日持仓报告包含：

1. **总体情况**
   - 持仓股票数
   - 总成本 / 总市值
   - 总盈亏（金额 + 百分比）

2. **持仓明细表**
   - 每只股票的盈亏情况
   - 综合评分
   - 交易建议

3. **交易建议**
   - 🔴 建议卖出列表（含原因）
   - 🟢 建议加仓列表（含原因）
   - ⚪ 持有观望列表

4. **新投资机会**
   - 推荐股票及理由
   - 综合评分排序

---

## 🚀 推荐工作流

### 方案A: 简单模式（新手）

```bash
# 每天早上看看自己关注的股票
python quick_analysis.py SH600000 SH600036 SH510300 --report

# 打开生成的 HTML 报告查看
open reports/quick_analysis_report.html
```

### 方案B: 持仓监控模式（推荐）

```bash
# 1. 创建持仓文件 my_portfolio.csv
# 2. 每天收盘后运行
python portfolio_monitor.py --portfolio my_portfolio.csv --daily-report

# 3. 打开 HTML 报告查看交易建议
open reports/daily_portfolio_report.html

# 4. 根据建议执行交易
```

### 方案C: 全自动模式（高级）

```bash
# 1. 配置 config.yaml
# 2. 配置定时任务
bash setup_cron.sh

# 3. 系统每天自动运行，发送报告
# 你只需要查看邮件/报告，做决策即可
```

---

## 💡 使用建议

1. **先模拟**: 用小仓位或模拟盘测试几周，观察建议的准确性
2. **不盲从**: 程序只是辅助工具，最终决策应结合自己的判断
3. **设止损**: 严格执行止损策略，控制风险
4. **分散投资**: 不要把所有资金投入单只股票
5. **长期视角**: 短期波动是正常的，关注长期趋势

---

## 📚 更多功能

查看详细文档：
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - 完整实现方案
- [README.md](README.md) - 系统说明
- [config.yaml](config.yaml) - 配置参数说明

---

## ⚠️ 免责声明

本工具仅供学习和研究使用，不构成投资建议。

投资有风险，决策需谨慎。使用本工具造成的任何损失，开发者不承担责任。
