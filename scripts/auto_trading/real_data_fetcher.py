#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实数据获取器

支持多种数据源：
1. Yahoo Finance - 免费，无需API key，适合美股/港股/部分A股ETF
2. Tushare - 需要token，专业A股数据

使用方法:
    # Yahoo Finance (无需配置)
    python real_data_fetcher.py --source yahoo --codes 600000.SS 000001.SZ --days 365

    # Tushare (需要token)
    python real_data_fetcher.py --source tushare --codes 600000.SH 000001.SZ --days 365 --token YOUR_TOKEN

    # 测试策略
    python real_data_fetcher.py --source yahoo --test-strategy dual_ma
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sys
import time

# 添加路径
sys.path.append(str(Path(__file__).parent))


class YahooFinanceDataFetcher:
    """
    Yahoo Finance 数据获取器

    优点：免费，无需API key
    缺点：A股数据可能不完整，延迟较大

    股票代码格式：
    - A股上海: 600000.SS
    - A股深圳: 000001.SZ
    - 港股: 0700.HK
    - 美股: AAPL
    """

    def __init__(self):
        self.name = "Yahoo Finance"
        self._check_yfinance()

    def _check_yfinance(self):
        """检查是否安装了yfinance"""
        try:
            import yfinance as yf
            self.yf = yf
            print(f"✅ yfinance 已安装")
        except ImportError:
            print("❌ 请先安装 yfinance: pip install yfinance")
            self.yf = None

    def fetch_single_stock(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取单个股票数据

        参数:
            code: 股票代码 (如 600000.SS)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        返回:
            DataFrame with columns ['code', 'date', 'open', 'high', 'low', 'close', 'volume']
        """
        if self.yf is None:
            return pd.DataFrame()

        try:
            ticker = self.yf.Ticker(code)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                print(f"  ⚠️ {code}: 无数据")
                return pd.DataFrame()

            # 重命名列
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # 添加股票代码
            df['code'] = code

            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 选择需要的列
            df = df[['code', 'date', 'open', 'high', 'low', 'close', 'volume']]

            # 四舍五入
            df['open'] = df['open'].round(2)
            df['high'] = df['high'].round(2)
            df['low'] = df['low'].round(2)
            df['close'] = df['close'].round(2)
            df['volume'] = df['volume'].astype(int)

            print(f"  ✅ {code}: {len(df)} 天数据")
            return df

        except Exception as e:
            print(f"  ❌ {code}: {str(e)[:50]}")
            return pd.DataFrame()

    def fetch_multiple_stocks(self, codes: list, start_date: str, end_date: str,
                             delay: float = 0.5) -> pd.DataFrame:
        """
        获取多个股票数据

        参数:
            codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            delay: 请求间隔（秒）

        返回:
            合并的DataFrame
        """
        print(f"\n📥 从 Yahoo Finance 获取数据...")
        print(f"股票数量: {len(codes)}")
        print(f"时间范围: {start_date} 至 {end_date}")

        all_data = []

        for i, code in enumerate(codes):
            print(f"  ({i+1}/{len(codes)}) 获取 {code}...", end="")
            df = self.fetch_single_stock(code, start_date, end_date)

            if not df.empty:
                all_data.append(df)

            if i < len(codes) - 1:
                time.sleep(delay)

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            print(f"\n✅ 成功获取 {len(all_data)} 只股票数据，共 {len(result)} 条记录")
            return result
        else:
            print("\n❌ 未能获取任何数据")
            return pd.DataFrame()

    @staticmethod
    def convert_a_share_code(code: str) -> str:
        """
        转换A股代码为Yahoo格式

        输入: SH600000 或 600000.SH 或 SZ000001 或 000001.SZ
        输出: 600000.SS 或 000001.SZ
        """
        code = code.upper().strip()

        # 处理 SH600000 格式
        if code.startswith('SH'):
            return code[2:] + '.SS'
        elif code.startswith('SZ'):
            return code[2:] + '.SZ'

        # 处理 600000.SH 格式
        if '.SH' in code:
            return code.replace('.SH', '.SS')
        elif '.SS' in code or '.SZ' in code:
            return code  # 已经是Yahoo格式

        # 根据代码判断交易所
        if code.startswith('6'):
            return code + '.SS'  # 上海
        elif code.startswith('0') or code.startswith('3'):
            return code + '.SZ'  # 深圳

        return code


class TushareDataFetcher:
    """
    Tushare 数据获取器

    优点：专业A股数据，数据全面准确
    缺点：需要注册token，部分接口需要积分

    注册地址：https://tushare.pro/register?reg=7

    股票代码格式：
    - A股上海: 600000.SH
    - A股深圳: 000001.SZ
    """

    def __init__(self, token: str = None):
        self.name = "Tushare"
        self.token = token
        self._check_tushare()

    def _check_tushare(self):
        """检查是否安装了tushare"""
        try:
            import tushare as ts
            self.ts = ts

            if self.token:
                ts.set_token(self.token)
                self.pro = ts.pro_api()
                print(f"✅ tushare 已配置token")
            else:
                self.pro = None
                print(f"⚠️ tushare 未配置token，部分功能受限")
        except ImportError:
            print("❌ 请先安装 tushare: pip install tushare")
            self.ts = None
            self.pro = None

    def fetch_single_stock(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取单个股票数据

        参数:
            code: 股票代码 (如 600000.SH)
            start_date: 开始日期 YYYY-MM-DD (会转换为YYYYMMDD)
            end_date: 结束日期 YYYY-MM-DD

        返回:
            DataFrame with columns ['code', 'date', 'open', 'high', 'low', 'close', 'volume']
        """
        if self.pro is None:
            print("  ❌ Tushare Pro API未初始化，请提供token")
            return pd.DataFrame()

        try:
            # 转换日期格式
            start_ts = start_date.replace('-', '')
            end_ts = end_date.replace('-', '')

            # 获取日线数据
            df = self.pro.daily(ts_code=code, start_date=start_ts, end_date=end_ts)

            if df.empty:
                print(f"  ⚠️ {code}: 无数据")
                return pd.DataFrame()

            # 重命名列
            df = df.rename(columns={
                'ts_code': 'code',
                'trade_date': 'date',
                'vol': 'volume'
            })

            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 选择需要的列
            df = df[['code', 'date', 'open', 'high', 'low', 'close', 'volume']]

            # 成交量单位转换（tushare单位为手，需转为股）
            df['volume'] = (df['volume'] * 100).astype(int)

            # 按日期排序
            df = df.sort_values('date').reset_index(drop=True)

            print(f"  ✅ {code}: {len(df)} 天数据")
            return df

        except Exception as e:
            print(f"  ❌ {code}: {str(e)[:50]}")
            return pd.DataFrame()

    def fetch_multiple_stocks(self, codes: list, start_date: str, end_date: str,
                             delay: float = 0.3) -> pd.DataFrame:
        """
        获取多个股票数据

        参数:
            codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            delay: 请求间隔（秒）

        返回:
            合并的DataFrame
        """
        print(f"\n📥 从 Tushare 获取数据...")
        print(f"股票数量: {len(codes)}")
        print(f"时间范围: {start_date} 至 {end_date}")

        all_data = []

        for i, code in enumerate(codes):
            print(f"  ({i+1}/{len(codes)}) 获取 {code}...", end="")
            df = self.fetch_single_stock(code, start_date, end_date)

            if not df.empty:
                all_data.append(df)

            if i < len(codes) - 1:
                time.sleep(delay)

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            print(f"\n✅ 成功获取 {len(all_data)} 只股票数据，共 {len(result)} 条记录")
            return result
        else:
            print("\n❌ 未能获取任何数据")
            return pd.DataFrame()

    @staticmethod
    def convert_a_share_code(code: str) -> str:
        """
        转换A股代码为Tushare格式

        输入: SH600000 或 600000.SS 或 600000
        输出: 600000.SH
        """
        code = code.upper().strip()

        # 处理 SH600000 格式
        if code.startswith('SH'):
            return code[2:] + '.SH'
        elif code.startswith('SZ'):
            return code[2:] + '.SZ'

        # 处理Yahoo格式
        if '.SS' in code:
            return code.replace('.SS', '.SH')
        elif '.SH' in code or '.SZ' in code:
            return code  # 已经是Tushare格式

        # 根据代码判断交易所
        if code.startswith('6'):
            return code + '.SH'  # 上海
        elif code.startswith('0') or code.startswith('3'):
            return code + '.SZ'  # 深圳

        return code


class RealDataFetcher:
    """
    统一的真实数据获取接口
    """

    def __init__(self, source: str = 'yahoo', tushare_token: str = None):
        """
        初始化数据获取器

        参数:
            source: 'yahoo' 或 'tushare'
            tushare_token: Tushare API token
        """
        self.source = source

        if source == 'yahoo':
            self.fetcher = YahooFinanceDataFetcher()
        elif source == 'tushare':
            self.fetcher = TushareDataFetcher(token=tushare_token)
        else:
            raise ValueError(f"不支持的数据源: {source}")

    def fetch_data(self, codes: list, days: int = 365,
                   end_date: str = None) -> pd.DataFrame:
        """
        获取历史数据

        参数:
            codes: 股票代码列表
            days: 获取天数
            end_date: 结束日期（默认今天）

        返回:
            DataFrame with OHLCV data
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        start_date = (datetime.strptime(end_date, '%Y-%m-%d') -
                     timedelta(days=days)).strftime('%Y-%m-%d')

        # 转换代码格式
        converted_codes = []
        for code in codes:
            if self.source == 'yahoo':
                converted_codes.append(YahooFinanceDataFetcher.convert_a_share_code(code))
            else:
                converted_codes.append(TushareDataFetcher.convert_a_share_code(code))

        return self.fetcher.fetch_multiple_stocks(converted_codes, start_date, end_date)

    def save_data(self, data: pd.DataFrame, filename: str = 'real_market_data.csv'):
        """保存数据到CSV"""
        output_path = Path(__file__).parent / filename
        data.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✅ 数据已保存: {output_path}")

    def load_data(self, filename: str = 'real_market_data.csv') -> pd.DataFrame:
        """从CSV加载数据"""
        file_path = Path(__file__).parent / filename
        if file_path.exists():
            data = pd.read_csv(file_path)
            print(f"✅ 数据已加载: {file_path}")
            return data
        else:
            print(f"❌ 文件不存在: {file_path}")
            return pd.DataFrame()


def test_strategy_with_real_data(data: pd.DataFrame, strategy_name: str = 'dual_ma'):
    """
    使用真实数据测试策略

    参数:
        data: 真实市场数据
        strategy_name: 策略名称
    """
    print(f"\n🧪 使用真实数据测试 {strategy_name} 策略...")

    if data.empty:
        print("❌ 没有数据可供测试")
        return

    # 获取日期范围
    dates = sorted(data['date'].unique())
    if len(dates) < 60:
        print(f"❌ 数据不足，需要至少60天，当前只有{len(dates)}天")
        return

    # 使用中间60%的数据进行回测
    start_idx = int(len(dates) * 0.2)
    end_idx = int(len(dates) * 0.8)
    start_date = dates[start_idx]
    end_date = dates[end_idx]

    print(f"回测区间: {start_date} 至 {end_date}")
    print(f"股票数量: {data['code'].nunique()}")

    # 导入策略
    try:
        if strategy_name == 'dual_ma':
            from strategies.dual_ma_strategy import DualMAStrategy
            strategy = DualMAStrategy(short_window=5, long_window=20)
        elif strategy_name == 'momentum':
            from strategies.momentum_strategy import MomentumStrategy
            strategy = MomentumStrategy(lookback_period=20)
        elif strategy_name == 'mean_reversion':
            from strategies.mean_reversion_strategy import MeanReversionStrategy
            strategy = MeanReversionStrategy(window=20)
        elif strategy_name == 'alpha101':
            from strategies.alpha101_strategy import Alpha101Strategy
            strategy = Alpha101Strategy()
        else:
            print(f"❌ 未知策略: {strategy_name}")
            return

        # 运行回测
        result = strategy.backtest(
            data=data,
            start_date=start_date,
            end_date=end_date,
            initial_capital=1000000,
            topk=min(10, data['code'].nunique())
        )

        # 打印结果
        print("\n📊 回测结果:")
        print(f"  总收益率: {result['total_return']*100:.2f}%")
        print(f"  年化收益率: {result['annual_return']*100:.2f}%")
        print(f"  夏普比率: {result['sharpe_ratio']:.4f}")
        print(f"  最大回撤: {result['max_drawdown']*100:.2f}%")
        print(f"  交易次数: {result['total_trades']}")
        print(f"  最终市值: ¥{result['final_value']:,.0f}")

    except ImportError as e:
        print(f"❌ 导入策略失败: {str(e)}")
    except Exception as e:
        print(f"❌ 回测失败: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description='真实数据获取器')
    parser.add_argument('--source', type=str, default='yahoo',
                       choices=['yahoo', 'tushare'],
                       help='数据源 (yahoo 或 tushare)')
    parser.add_argument('--codes', nargs='+', type=str,
                       default=['600000', '000001', '600036', '601318', '600519'],
                       help='股票代码列表')
    parser.add_argument('--days', type=int, default=365,
                       help='获取天数')
    parser.add_argument('--token', type=str, default=None,
                       help='Tushare token')
    parser.add_argument('--save', type=str, default='real_market_data.csv',
                       help='保存文件名')
    parser.add_argument('--test-strategy', type=str, default=None,
                       choices=['dual_ma', 'momentum', 'mean_reversion', 'alpha101'],
                       help='测试策略')

    args = parser.parse_args()

    print("=" * 60)
    print("📊 真实数据获取器")
    print("=" * 60)

    # 创建数据获取器
    fetcher = RealDataFetcher(source=args.source, tushare_token=args.token)

    # 获取数据
    data = fetcher.fetch_data(codes=args.codes, days=args.days)

    if not data.empty:
        # 保存数据
        fetcher.save_data(data, args.save)

        # 数据统计
        print("\n📈 数据统计:")
        print(f"  股票数量: {data['code'].nunique()}")
        print(f"  总记录数: {len(data)}")
        print(f"  日期范围: {data['date'].min()} 至 {data['date'].max()}")

        # 测试策略
        if args.test_strategy:
            test_strategy_with_real_data(data, args.test_strategy)

    print("\n🎉 完成！")


if __name__ == '__main__':
    main()
