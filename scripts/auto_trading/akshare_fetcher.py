#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare 数据获取器

免费开源的 A股/ETF/港股 数据获取模块
支持实时行情、历史K线、财务数据、资金流向等

使用方法:
    # 获取A股日线数据
    python akshare_fetcher.py --type stock --codes 600000 000001 --days 365

    # 获取ETF数据
    python akshare_fetcher.py --type etf --codes 510300 510500 --days 365

    # 获取实时行情
    python akshare_fetcher.py --type realtime --codes 600000 000001

    # 获取资金流向
    python akshare_fetcher.py --type money_flow --codes 600000
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sys
import time
import warnings

warnings.filterwarnings('ignore')

# 添加路径
sys.path.append(str(Path(__file__).parent))


class AKShareDataFetcher:
    """
    AKShare 数据获取器

    特点：
    - 完全免费，无积分限制
    - 数据源：东方财富、新浪财经、金十数据等
    - 支持：A股、港股、ETF、期货、基金
    - 实时行情 + 历史数据 + 财务数据 + 资金流向

    A股代码格式：
    - 上海: 600000, 601318
    - 深圳: 000001, 002594
    - 科创板: 688001
    - 创业板: 300001

    ETF代码格式：
    - 上海: 510300, 510500
    - 深圳: 159915, 159919
    """

    def __init__(self, cache_dir: str = "./data/akshare_cache"):
        """
        初始化 AKShare 数据获取器

        Args:
            cache_dir: 数据缓存目录
        """
        self.name = "AKShare"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._check_akshare()

    def _check_akshare(self):
        """检查是否安装了akshare"""
        try:
            import akshare as ak
            self.ak = ak
            version = ak.__version__
            print(f"✅ AKShare {version} 已安装")
        except ImportError:
            print("❌ 请先安装 akshare: pip install akshare")
            self.ak = None

    def _normalize_stock_code(self, code: str) -> str:
        """
        标准化股票代码（去除前缀）

        Args:
            code: 原始代码 (如 SH600000, 600000.SH, 600000)

        Returns:
            标准化代码 (如 600000)
        """
        code = str(code).strip()
        # 移除常见前缀
        for prefix in ['SH', 'SZ', 'sh', 'sz', '.SS', '.SZ']:
            code = code.replace(prefix, '')
        # 移除后缀
        if '.' in code:
            code = code.split('.')[0]
        return code

    def _get_market_prefix(self, code: str) -> str:
        """
        根据代码获取市场前缀

        Args:
            code: 标准化股票代码

        Returns:
            市场前缀 (sh/sz)
        """
        code = self._normalize_stock_code(code)
        if code.startswith(('6', '5', '9')):
            return 'sh'
        else:
            return 'sz'

    def fetch_stock_history(self, code: str, start_date: str = None,
                            end_date: str = None, days: int = 365,
                            adjust: str = "qfq") -> pd.DataFrame:
        """
        获取A股历史日线数据

        Args:
            code: 股票代码 (如 600000)
            start_date: 开始日期 YYYY-MM-DD (可选)
            end_date: 结束日期 YYYY-MM-DD (可选)
            days: 获取最近N天数据 (当start_date未指定时使用)
            adjust: 复权类型 (qfq=前复权, hfq=后复权, 空=不复权)

        Returns:
            DataFrame with columns ['code', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        """
        if self.ak is None:
            return pd.DataFrame()

        code = self._normalize_stock_code(code)

        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        else:
            end_date = end_date.replace('-', '')

        if start_date is None:
            start_dt = datetime.now() - timedelta(days=days)
            start_date = start_dt.strftime('%Y%m%d')
        else:
            start_date = start_date.replace('-', '')

        try:
            # 使用东方财富数据源
            df = self.ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )

            if df.empty:
                print(f"  ⚠️ {code}: 无数据")
                return pd.DataFrame()

            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })

            # 添加股票代码
            df['code'] = code

            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # 选择需要的列
            columns = ['code', 'date', 'open', 'high', 'low', 'close', 'volume']
            if 'amount' in df.columns:
                columns.append('amount')
            if 'pct_change' in df.columns:
                columns.append('pct_change')
            if 'turnover' in df.columns:
                columns.append('turnover')

            df = df[columns]

            print(f"  ✅ {code}: 获取 {len(df)} 条数据 ({df['date'].iloc[0]} ~ {df['date'].iloc[-1]})")
            return df

        except Exception as e:
            print(f"  ❌ {code}: 获取失败 - {str(e)}")
            return pd.DataFrame()

    def fetch_etf_history(self, code: str, start_date: str = None,
                          end_date: str = None, days: int = 365) -> pd.DataFrame:
        """
        获取ETF历史日线数据

        Args:
            code: ETF代码 (如 510300)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            days: 获取最近N天数据

        Returns:
            DataFrame
        """
        if self.ak is None:
            return pd.DataFrame()

        code = self._normalize_stock_code(code)

        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        else:
            end_date = end_date.replace('-', '')

        if start_date is None:
            start_dt = datetime.now() - timedelta(days=days)
            start_date = start_dt.strftime('%Y%m%d')
        else:
            start_date = start_date.replace('-', '')

        try:
            # 使用东方财富ETF数据
            df = self.ak.fund_etf_hist_em(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )

            if df.empty:
                print(f"  ⚠️ ETF {code}: 无数据")
                return pd.DataFrame()

            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })

            df['code'] = code
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            columns = ['code', 'date', 'open', 'high', 'low', 'close', 'volume']
            if 'amount' in df.columns:
                columns.append('amount')
            if 'pct_change' in df.columns:
                columns.append('pct_change')

            df = df[columns]

            print(f"  ✅ ETF {code}: 获取 {len(df)} 条数据 ({df['date'].iloc[0]} ~ {df['date'].iloc[-1]})")
            return df

        except Exception as e:
            print(f"  ❌ ETF {code}: 获取失败 - {str(e)}")
            return pd.DataFrame()

    def fetch_realtime_quotes(self, codes: list) -> pd.DataFrame:
        """
        获取实时行情数据

        Args:
            codes: 股票代码列表

        Returns:
            DataFrame with realtime quotes
        """
        if self.ak is None:
            return pd.DataFrame()

        try:
            # 获取全部A股实时行情
            df = self.ak.stock_zh_a_spot_em()

            # 标准化代码
            normalized_codes = [self._normalize_stock_code(c) for c in codes]

            # 筛选指定股票
            df = df[df['代码'].isin(normalized_codes)]

            if df.empty:
                print(f"  ⚠️ 未找到指定股票的实时数据")
                return pd.DataFrame()

            # 重命名列
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '最高': 'high',
                '最低': 'low',
                '今开': 'open',
                '昨收': 'pre_close',
                '量比': 'volume_ratio',
                '换手率': 'turnover',
                '市盈率-动态': 'pe_ratio',
                '市净率': 'pb_ratio'
            })

            print(f"  ✅ 获取 {len(df)} 只股票实时行情")
            return df

        except Exception as e:
            print(f"  ❌ 获取实时行情失败: {str(e)}")
            return pd.DataFrame()

    def fetch_money_flow(self, code: str, days: int = 30) -> pd.DataFrame:
        """
        获取个股资金流向数据

        Args:
            code: 股票代码
            days: 获取最近N天数据

        Returns:
            DataFrame with money flow data
        """
        if self.ak is None:
            return pd.DataFrame()

        code = self._normalize_stock_code(code)
        market = self._get_market_prefix(code)

        try:
            # 获取个股资金流向
            df = self.ak.stock_individual_fund_flow(
                stock=code,
                market=market
            )

            if df.empty:
                print(f"  ⚠️ {code}: 无资金流向数据")
                return pd.DataFrame()

            # 只取最近N天
            df = df.head(days)

            df['code'] = code

            print(f"  ✅ {code}: 获取 {len(df)} 天资金流向数据")
            return df

        except Exception as e:
            print(f"  ❌ {code}: 获取资金流向失败 - {str(e)}")
            return pd.DataFrame()

    def fetch_financial_data(self, code: str) -> dict:
        """
        获取股票财务数据

        Args:
            code: 股票代码

        Returns:
            dict with financial metrics
        """
        if self.ak is None:
            return {}

        code = self._normalize_stock_code(code)

        try:
            # 获取个股基本面信息
            df = self.ak.stock_individual_info_em(symbol=code)

            if df.empty:
                return {}

            # 转换为字典
            result = {}
            for _, row in df.iterrows():
                result[row['item']] = row['value']

            print(f"  ✅ {code}: 获取财务数据成功")
            return result

        except Exception as e:
            print(f"  ❌ {code}: 获取财务数据失败 - {str(e)}")
            return {}

    def fetch_market_sentiment(self) -> dict:
        """
        获取市场情绪指标

        Returns:
            dict with market sentiment data
        """
        if self.ak is None:
            return {}

        try:
            result = {}

            # 涨跌停统计
            try:
                limit_up = self.ak.stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))
                result['limit_up_count'] = len(limit_up) if not limit_up.empty else 0
            except:
                result['limit_up_count'] = 0

            # 市场概况
            try:
                overview = self.ak.stock_market_activity_legu()
                if not overview.empty:
                    result['up_count'] = overview.iloc[0].get('上涨', 0)
                    result['down_count'] = overview.iloc[0].get('下跌', 0)
                    result['flat_count'] = overview.iloc[0].get('平盘', 0)
            except:
                pass

            print(f"  ✅ 获取市场情绪数据成功")
            return result

        except Exception as e:
            print(f"  ❌ 获取市场情绪失败: {str(e)}")
            return {}

    def fetch_multiple_stocks(self, codes: list, data_type: str = "stock",
                              days: int = 365, delay: float = 0.3) -> pd.DataFrame:
        """
        批量获取多只股票数据

        Args:
            codes: 股票代码列表
            data_type: 数据类型 (stock/etf)
            days: 获取天数
            delay: 请求间隔（秒）

        Returns:
            合并的DataFrame
        """
        all_data = []

        print(f"\n📊 开始获取 {len(codes)} 只{data_type}数据...")

        for i, code in enumerate(codes, 1):
            print(f"[{i}/{len(codes)}] 正在获取 {code}...")

            if data_type == "etf":
                df = self.fetch_etf_history(code, days=days)
            else:
                df = self.fetch_stock_history(code, days=days)

            if not df.empty:
                all_data.append(df)

            # 避免请求过快
            if i < len(codes):
                time.sleep(delay)

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            print(f"\n✅ 完成! 共获取 {len(result)} 条数据")
            return result
        else:
            print(f"\n⚠️ 未获取到任何数据")
            return pd.DataFrame()

    def save_to_cache(self, df: pd.DataFrame, filename: str):
        """保存数据到缓存"""
        if df.empty:
            return

        filepath = self.cache_dir / filename
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"💾 数据已保存到: {filepath}")

    def load_from_cache(self, filename: str) -> pd.DataFrame:
        """从缓存加载数据"""
        filepath = self.cache_dir / filename
        if filepath.exists():
            df = pd.read_csv(filepath)
            print(f"📂 从缓存加载: {filepath}")
            return df
        return pd.DataFrame()

    def get_stock_list(self, market: str = "all") -> pd.DataFrame:
        """
        获取股票列表

        Args:
            market: 市场 (all/sh/sz/kc/cy)

        Returns:
            DataFrame with stock list
        """
        if self.ak is None:
            return pd.DataFrame()

        try:
            df = self.ak.stock_zh_a_spot_em()

            if market == "sh":
                df = df[df['代码'].str.startswith('6')]
            elif market == "sz":
                df = df[df['代码'].str.startswith(('0', '3'))]
            elif market == "kc":  # 科创板
                df = df[df['代码'].str.startswith('688')]
            elif market == "cy":  # 创业板
                df = df[df['代码'].str.startswith('3')]

            result = df[['代码', '名称']].copy()
            result.columns = ['code', 'name']

            print(f"✅ 获取 {len(result)} 只股票列表")
            return result

        except Exception as e:
            print(f"❌ 获取股票列表失败: {str(e)}")
            return pd.DataFrame()

    def get_etf_list(self) -> pd.DataFrame:
        """
        获取ETF列表

        Returns:
            DataFrame with ETF list
        """
        if self.ak is None:
            return pd.DataFrame()

        try:
            df = self.ak.fund_etf_spot_em()

            result = df[['代码', '名称']].copy()
            result.columns = ['code', 'name']

            print(f"✅ 获取 {len(result)} 只ETF列表")
            return result

        except Exception as e:
            print(f"❌ 获取ETF列表失败: {str(e)}")
            return pd.DataFrame()

    def check_data_freshness(self) -> dict:
        """
        检查数据新鲜度

        Returns:
            dict with data freshness info
        """
        result = {
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sources': {}
        }

        if self.ak is None:
            return result

        try:
            # 检查A股数据
            df = self.fetch_stock_history('600000', days=5)
            if not df.empty:
                latest_date = df['date'].max()
                result['sources']['A股'] = {
                    'latest_date': latest_date,
                    'sample_stock': '600000'
                }

            # 检查ETF数据
            df = self.fetch_etf_history('510300', days=5)
            if not df.empty:
                latest_date = df['date'].max()
                result['sources']['ETF'] = {
                    'latest_date': latest_date,
                    'sample_etf': '510300'
                }

        except Exception as e:
            result['error'] = str(e)

        return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AKShare 数据获取器')
    parser.add_argument('--type', choices=['stock', 'etf', 'realtime', 'money_flow', 'check'],
                       default='stock', help='数据类型')
    parser.add_argument('--codes', nargs='+', default=['600000', '000001'],
                       help='股票代码列表')
    parser.add_argument('--days', type=int, default=365, help='获取天数')
    parser.add_argument('--save', action='store_true', help='保存到缓存')

    args = parser.parse_args()

    fetcher = AKShareDataFetcher()

    if args.type == 'check':
        # 检查数据新鲜度
        print("\n🔍 检查数据新鲜度...")
        result = fetcher.check_data_freshness()
        print(f"\n检查时间: {result['check_time']}")
        for source, info in result.get('sources', {}).items():
            print(f"\n{source}:")
            for key, value in info.items():
                print(f"  {key}: {value}")

    elif args.type == 'realtime':
        # 获取实时行情
        df = fetcher.fetch_realtime_quotes(args.codes)
        if not df.empty:
            print(df)
            if args.save:
                fetcher.save_to_cache(df, 'realtime_quotes.csv')

    elif args.type == 'money_flow':
        # 获取资金流向
        for code in args.codes:
            df = fetcher.fetch_money_flow(code, args.days)
            if not df.empty:
                print(df.head(10))
                if args.save:
                    fetcher.save_to_cache(df, f'money_flow_{code}.csv')

    elif args.type == 'etf':
        # 获取ETF数据
        df = fetcher.fetch_multiple_stocks(args.codes, data_type='etf', days=args.days)
        if not df.empty and args.save:
            fetcher.save_to_cache(df, 'etf_data.csv')

    else:
        # 获取股票数据
        df = fetcher.fetch_multiple_stocks(args.codes, data_type='stock', days=args.days)
        if not df.empty and args.save:
            fetcher.save_to_cache(df, 'stock_data.csv')


if __name__ == "__main__":
    main()
