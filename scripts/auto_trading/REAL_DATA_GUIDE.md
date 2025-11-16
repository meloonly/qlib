# 真实数据集成指南

本指南介绍如何获取真实市场数据并用于策略回测。

## 📚 支持的数据源

### 1️⃣ Yahoo Finance（推荐入门）

**优点**:
- ✅ 免费，无需API key
- ✅ 支持全球市场（美股、港股、A股ETF）
- ✅ 数据可靠

**缺点**:
- ❌ A股数据可能不完整
- ❌ 某些地区可能有访问限制
- ❌ 数据延迟约15-20分钟

**安装**:
```bash
pip install yfinance
```

**使用方法**:
```python
from real_data_fetcher import RealDataFetcher

# 创建数据获取器
fetcher = RealDataFetcher(source='yahoo')

# 获取美股数据
us_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
data = fetcher.fetch_data(codes=us_stocks, days=365)

# 获取港股数据
hk_stocks = ['0700', '9988', '3690']  # 腾讯、阿里、美团
data = fetcher.fetch_data(codes=hk_stocks, days=365)

# 获取A股ETF
a_share_etf = ['510300', '510050', '159915']  # 沪深300, 上证50, 创业板
data = fetcher.fetch_data(codes=a_share_etf, days=365)

# 保存数据
fetcher.save_data(data, 'market_data.csv')
```

**股票代码格式**:
| 市场 | 格式 | 示例 |
|------|------|------|
| 美股 | 直接使用 | AAPL, MSFT |
| 港股 | 代码 | 0700, 9988 |
| A股(上海) | SH600000 或 600000 | SH600036, 600036 |
| A股(深圳) | SZ000001 或 000001 | SZ000001, 000858 |

---

### 2️⃣ Tushare（专业A股数据）

**优点**:
- ✅ 专业的A股数据
- ✅ 数据全面准确
- ✅ 支持更多数据类型（财务、分红、公告等）

**缺点**:
- ❌ 需要注册获取token
- ❌ 部分高级接口需要积分
- ❌ 免费用户有调用频率限制

**注册地址**: [https://tushare.pro/register](https://tushare.pro/register?reg=7)

**安装**:
```bash
pip install tushare
```

**获取Token**:
1. 注册Tushare账号
2. 登录后进入个人中心
3. 复制API Token

**使用方法**:
```python
from real_data_fetcher import RealDataFetcher

# 创建数据获取器（需要token）
fetcher = RealDataFetcher(source='tushare', tushare_token='YOUR_TOKEN_HERE')

# 获取A股数据
a_shares = ['600000', '000001', '600036', '601318', '600519']
data = fetcher.fetch_data(codes=a_shares, days=365)

# 保存数据
fetcher.save_data(data, 'a_share_data.csv')
```

**股票代码格式**:
| 交易所 | 格式 | 示例 |
|--------|------|------|
| 上海 | 600000.SH 或 SH600000 | 600036.SH, SH600519 |
| 深圳 | 000001.SZ 或 SZ000001 | 000858.SZ, SZ002594 |

---

## 🚀 命令行使用

```bash
cd scripts/auto_trading

# Yahoo Finance 获取美股
python real_data_fetcher.py --source yahoo --codes AAPL MSFT GOOGL --days 365

# Yahoo Finance 获取港股
python real_data_fetcher.py --source yahoo --codes 0700.HK 9988.HK --days 365

# Tushare 获取A股（需要token）
python real_data_fetcher.py --source tushare --codes 600000 000001 600036 --days 365 --token YOUR_TOKEN

# 获取数据并测试策略
python real_data_fetcher.py --source yahoo --codes AAPL MSFT GOOGL AMZN META --days 500 --test-strategy dual_ma

# 测试其他策略
python real_data_fetcher.py --source yahoo --codes AAPL MSFT --test-strategy momentum
python real_data_fetcher.py --source yahoo --codes AAPL MSFT --test-strategy mean_reversion
```

---

## 📊 与策略集成

### 方法1: 直接使用真实数据回测

```python
from real_data_fetcher import RealDataFetcher
from strategies.dual_ma_strategy import DualMAStrategy

# 1. 获取数据
fetcher = RealDataFetcher(source='yahoo')
data = fetcher.fetch_data(codes=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'], days=500)

# 2. 设置回测区间
dates = sorted(data['date'].unique())
start_date = dates[100]  # 留出历史数据
end_date = dates[-1]

# 3. 运行策略回测
strategy = DualMAStrategy(short_window=5, long_window=20)
result = strategy.backtest(
    data=data,
    start_date=start_date,
    end_date=end_date,
    initial_capital=1000000,
    topk=5
)

# 4. 查看结果
print(f"总收益率: {result['total_return']*100:.2f}%")
print(f"夏普比率: {result['sharpe_ratio']:.4f}")
print(f"最大回撤: {result['max_drawdown']*100:.2f}%")
```

### 方法2: 加载已保存的数据

```python
from real_data_fetcher import RealDataFetcher
from strategies.momentum_strategy import MomentumStrategy

# 1. 加载数据
fetcher = RealDataFetcher(source='yahoo')
data = fetcher.load_data('market_data.csv')

# 2. 运行策略
strategy = MomentumStrategy(lookback_period=20, holding_period=5)
result = strategy.backtest(
    data=data,
    start_date='2024-01-01',
    end_date='2024-12-31',
    initial_capital=1000000
)
```

### 方法3: 使用参数优化器

```python
from real_data_fetcher import RealDataFetcher
from parameter_optimizer import ParameterOptimizer

# 1. 获取真实数据
fetcher = RealDataFetcher(source='yahoo')
data = fetcher.fetch_data(codes=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'], days=500)

# 2. 创建优化器
optimizer = ParameterOptimizer()
optimizer.optimization_results = {}

# 3. 设置日期
dates = sorted(data['date'].unique())
start_date = dates[100]
end_date = dates[-1]

# 4. 优化双均线策略
optimizer.optimize_dual_ma(data, start_date, end_date, topk=5)

# 5. 查看最优参数
optimizer.find_best_params(target='sharpe_ratio')
```

---

## 📈 推荐的股票池

### 美股（Yahoo Finance）

**大型科技股**:
```python
codes = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA']
```

**道琼斯30**:
```python
codes = ['AAPL', 'MSFT', 'JNJ', 'V', 'WMT', 'JPM', 'UNH', 'HD', 'PG', 'MA']
```

**ETF**:
```python
codes = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI']  # 主要指数ETF
```

### A股（Tushare）

**沪深300成分股（部分）**:
```python
codes = ['600000', '600036', '601318', '600519', '000858',
         '000001', '002594', '600030', '601166', '601398']
```

**行业龙头**:
```python
codes = [
    '600519',  # 茅台（白酒）
    '601318',  # 平安（保险）
    '600036',  # 招商银行
    '000858',  # 五粮液
    '600276',  # 恒瑞医药
    '002475',  # 立讯精密
    '600887',  # 伊利股份
]
```

**ETF**:
```python
codes = ['510300', '510050', '159915', '510500', '512000']
```

### 港股（Yahoo Finance）

**互联网龙头**:
```python
codes = ['0700.HK', '9988.HK', '3690.HK', '1024.HK', '9999.HK']
# 腾讯、阿里、美团、快手、网易
```

---

## ⚠️ 注意事项

### 1. 数据质量检查
```python
# 检查缺失值
print(data.isnull().sum())

# 检查数据量
print(data.groupby('code').size())

# 检查价格异常
for code in data['code'].unique():
    stock_data = data[data['code'] == code]
    returns = stock_data['close'].pct_change()
    if returns.abs().max() > 0.2:  # 单日涨跌幅超过20%
        print(f"警告: {code} 存在异常涨跌幅")
```

### 2. 复权处理
- Yahoo Finance 返回的是**前复权**价格
- Tushare 默认返回**不复权**价格
- 回测时建议使用复权价格，避免除权缺口

### 3. 交易日历
- 不同市场交易日不同
- 确保回测区间内所有股票都有数据

### 4. API限制
- Yahoo Finance: 无明确限制，但建议添加延迟
- Tushare: 免费用户每分钟200次调用

### 5. 数据延迟
- 实时数据有15-20分钟延迟
- 建议使用历史数据进行策略研究

---

## 🔧 常见问题

### Q1: Yahoo Finance 返回空数据
**原因**: 代码格式不正确或网络限制
**解决**:
- 检查股票代码格式
- 尝试使用VPN
- 使用Tushare替代

### Q2: Tushare token无效
**原因**: token错误或过期
**解决**:
- 登录Tushare网站重新获取token
- 检查是否有多余空格

### Q3: 回测数据不足
**原因**: 获取的数据天数不够
**解决**:
- 增加获取天数（days参数）
- 确保至少有60天以上数据

### Q4: 策略表现不佳
**原因**:
- 参数不适合当前市场
- 数据量太少
- 市场环境变化

**解决**:
- 使用参数优化器调优
- 增加回测数据量
- 尝试不同策略组合

---

## 📚 扩展阅读

- [Yahoo Finance Python文档](https://pypi.org/project/yfinance/)
- [Tushare Pro 官方文档](https://tushare.pro/document/2)
- [量化投资入门](https://www.joinquant.com/study)

---

## 💡 最佳实践

1. **数据缓存**: 获取数据后保存到本地，避免重复请求
2. **增量更新**: 只获取新数据，与历史数据合并
3. **数据清洗**: 处理缺失值、异常值
4. **分批获取**: 大量股票时分批获取，避免超时
5. **日志记录**: 记录数据获取过程，便于排查问题

---

**投资有风险，入市需谨慎！**
历史表现不代表未来收益，请谨慎使用策略。
