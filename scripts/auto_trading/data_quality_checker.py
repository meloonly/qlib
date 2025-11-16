#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量检查器

检测数据中的缺失值、异常值、数据完整性等问题。
确保用于策略分析的数据质量可靠。

使用方法:
    from data_quality_checker import DataQualityChecker

    checker = DataQualityChecker()
    report = checker.check_data(df)
    checker.print_report(report)
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))


class DataQualityChecker:
    """
    数据质量检查器
    """

    def __init__(self, config: dict = None):
        """
        初始化检查器

        参数:
            config: 配置参数，如果为None则使用默认值
        """
        if config is None:
            config = {}

        self.min_data_days = config.get('min_data_days', 60)
        self.max_missing_pct = config.get('max_missing_pct', 0.05)
        self.max_price_change_pct = config.get('max_price_change_pct', 0.20)
        self.min_volume = config.get('min_volume', 100000)

    def check_data(self, data: pd.DataFrame) -> dict:
        """
        全面检查数据质量

        参数:
            data: DataFrame，必须包含列 ['code', 'date', 'open', 'high', 'low', 'close', 'volume']

        返回:
            检查报告字典
        """
        report = {
            'check_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_records': len(data),
            'total_stocks': data['code'].nunique() if 'code' in data.columns else 0,
            'date_range': {},
            'issues': [],
            'warnings': [],
            'passed': True,
            'stock_reports': {}
        }

        if data.empty:
            report['issues'].append("数据为空")
            report['passed'] = False
            return report

        # 检查必要的列
        required_columns = ['code', 'date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            report['issues'].append(f"缺少必要列: {missing_columns}")
            report['passed'] = False
            return report

        # 日期范围
        report['date_range'] = {
            'start': data['date'].min(),
            'end': data['date'].max(),
            'days': len(data['date'].unique())
        }

        # 逐股检查
        for code in data['code'].unique():
            stock_data = data[data['code'] == code].copy()
            stock_report = self._check_single_stock(code, stock_data)
            report['stock_reports'][code] = stock_report

            # 汇总问题
            if stock_report['issues']:
                report['issues'].extend([f"{code}: {issue}" for issue in stock_report['issues']])
            if stock_report['warnings']:
                report['warnings'].extend([f"{code}: {warning}" for warning in stock_report['warnings']])

        # 总体检查
        overall_issues = self._check_overall_data(data)
        report['issues'].extend(overall_issues['issues'])
        report['warnings'].extend(overall_issues['warnings'])

        # 更新通过状态
        if report['issues']:
            report['passed'] = False

        return report

    def _check_single_stock(self, code: str, data: pd.DataFrame) -> dict:
        """
        检查单个股票的数据质量

        参数:
            code: 股票代码
            data: 该股票的数据

        返回:
            股票检查报告
        """
        report = {
            'code': code,
            'records': len(data),
            'issues': [],
            'warnings': [],
            'stats': {}
        }

        # 1. 检查数据量
        if len(data) < self.min_data_days:
            report['issues'].append(f"数据不足: {len(data)}天 < {self.min_data_days}天")

        # 2. 检查缺失值
        missing_counts = data[['open', 'high', 'low', 'close', 'volume']].isnull().sum()
        total_missing = missing_counts.sum()
        missing_pct = total_missing / (len(data) * 5)
        report['stats']['missing_pct'] = missing_pct

        if missing_pct > self.max_missing_pct:
            report['issues'].append(f"缺失值过多: {missing_pct*100:.2f}% > {self.max_missing_pct*100:.0f}%")
        elif missing_pct > 0:
            report['warnings'].append(f"存在缺失值: {missing_pct*100:.2f}%")

        # 3. 检查价格异常
        data = data.sort_values('date')
        data['price_change'] = data['close'].pct_change()

        # 单日涨跌幅异常
        extreme_changes = data[data['price_change'].abs() > self.max_price_change_pct]
        if len(extreme_changes) > 0:
            report['warnings'].append(f"存在{len(extreme_changes)}个异常涨跌幅（>{self.max_price_change_pct*100:.0f}%）")
            report['stats']['extreme_changes'] = len(extreme_changes)

        # 价格为0或负数
        invalid_prices = (
            (data['close'] <= 0) | (data['open'] <= 0) |
            (data['high'] <= 0) | (data['low'] <= 0)
        ).sum()
        if invalid_prices > 0:
            report['issues'].append(f"存在{invalid_prices}个无效价格（≤0）")

        # 4. 检查OHLC逻辑
        invalid_ohlc = (
            (data['high'] < data['low']) |
            (data['high'] < data['open']) |
            (data['high'] < data['close']) |
            (data['low'] > data['open']) |
            (data['low'] > data['close'])
        ).sum()
        if invalid_ohlc > 0:
            report['warnings'].append(f"存在{invalid_ohlc}个OHLC逻辑错误")

        # 5. 检查成交量
        low_volume = (data['volume'] < self.min_volume).sum()
        if low_volume > len(data) * 0.5:
            report['warnings'].append(f"成交量普遍偏低: {low_volume}/{len(data)}天")

        zero_volume = (data['volume'] == 0).sum()
        if zero_volume > 0:
            report['warnings'].append(f"存在{zero_volume}个零成交量")

        # 6. 检查日期连续性
        data['date'] = pd.to_datetime(data['date'])
        date_gaps = data['date'].diff().dt.days
        large_gaps = (date_gaps > 10).sum()  # 超过10天的间隔
        if large_gaps > 0:
            report['warnings'].append(f"存在{large_gaps}个较大的日期间隔（>10天）")

        # 7. 检查重复数据
        duplicates = data.duplicated(subset=['date']).sum()
        if duplicates > 0:
            report['issues'].append(f"存在{duplicates}条重复日期记录")

        # 统计信息
        report['stats']['min_price'] = data['close'].min()
        report['stats']['max_price'] = data['close'].max()
        report['stats']['avg_volume'] = data['volume'].mean()
        report['stats']['price_volatility'] = data['price_change'].std()

        return report

    def _check_overall_data(self, data: pd.DataFrame) -> dict:
        """
        检查整体数据质量

        参数:
            data: 全部数据

        返回:
            整体检查报告
        """
        report = {
            'issues': [],
            'warnings': []
        }

        # 1. 检查股票数量分布
        stock_counts = data.groupby('code').size()
        if stock_counts.std() / stock_counts.mean() > 0.5:
            report['warnings'].append("各股票数据量差异较大")

        # 2. 检查日期一致性
        dates_per_stock = data.groupby('date')['code'].count()
        if dates_per_stock.std() / dates_per_stock.mean() > 0.3:
            report['warnings'].append("各日期的数据完整性不一致")

        # 3. 检查数据新鲜度
        latest_date = pd.to_datetime(data['date'].max())
        days_old = (datetime.now() - latest_date).days
        if days_old > 7:
            report['warnings'].append(f"数据较旧: 最新日期距今{days_old}天")
        elif days_old > 30:
            report['issues'].append(f"数据过旧: 最新日期距今{days_old}天")

        return report

    def clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        清洗数据，修复常见问题

        参数:
            data: 原始数据

        返回:
            清洗后的数据
        """
        print("🧹 清洗数据...")
        cleaned = data.copy()
        original_count = len(cleaned)

        # 1. 删除重复数据
        cleaned = cleaned.drop_duplicates(subset=['code', 'date'])
        duplicates_removed = original_count - len(cleaned)
        if duplicates_removed > 0:
            print(f"  删除重复记录: {duplicates_removed}")

        # 2. 删除无效价格
        invalid_mask = (
            (cleaned['close'] <= 0) | (cleaned['open'] <= 0) |
            (cleaned['high'] <= 0) | (cleaned['low'] <= 0)
        )
        invalid_count = invalid_mask.sum()
        cleaned = cleaned[~invalid_mask]
        if invalid_count > 0:
            print(f"  删除无效价格: {invalid_count}")

        # 3. 修复OHLC逻辑
        # High应该是最大值
        cleaned['high'] = cleaned[['open', 'high', 'low', 'close']].max(axis=1)
        # Low应该是最小值
        cleaned['low'] = cleaned[['open', 'high', 'low', 'close']].min(axis=1)

        # 4. 填充缺失值（使用前向填充）
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            missing_before = cleaned[col].isnull().sum()
            if missing_before > 0:
                cleaned[col] = cleaned.groupby('code')[col].ffill()
                missing_after = cleaned[col].isnull().sum()
                print(f"  填充 {col} 缺失值: {missing_before - missing_after}")

        # 5. 排序数据
        cleaned = cleaned.sort_values(['code', 'date']).reset_index(drop=True)

        print(f"  清洗完成: {original_count} -> {len(cleaned)} 条记录")
        return cleaned

    def filter_quality_stocks(self, data: pd.DataFrame, min_days: int = None) -> pd.DataFrame:
        """
        过滤出数据质量好的股票

        参数:
            data: 原始数据
            min_days: 最少数据天数

        返回:
            过滤后的数据
        """
        if min_days is None:
            min_days = self.min_data_days

        print(f"📊 过滤数据质量好的股票（最少{min_days}天数据）...")

        quality_stocks = []
        for code in data['code'].unique():
            stock_data = data[data['code'] == code]

            # 检查数据量
            if len(stock_data) < min_days:
                continue

            # 检查缺失值
            missing_pct = stock_data[['close', 'volume']].isnull().sum().sum() / (len(stock_data) * 2)
            if missing_pct > self.max_missing_pct:
                continue

            # 检查价格有效性
            if (stock_data['close'] <= 0).any():
                continue

            quality_stocks.append(code)

        print(f"  筛选结果: {len(quality_stocks)}/{data['code'].nunique()} 只股票通过质量检查")

        return data[data['code'].isin(quality_stocks)]

    def print_report(self, report: dict):
        """
        打印检查报告

        参数:
            report: 检查报告字典
        """
        print("\n" + "=" * 70)
        print("📋 数据质量检查报告")
        print("=" * 70)

        print(f"\n检查时间: {report['check_time']}")
        print(f"总记录数: {report['total_records']:,}")
        print(f"股票数量: {report['total_stocks']}")

        if report['date_range']:
            print(f"日期范围: {report['date_range']['start']} 至 {report['date_range']['end']}")
            print(f"数据天数: {report['date_range']['days']}")

        # 显示状态
        if report['passed']:
            print("\n✅ 数据质量检查通过")
        else:
            print("\n❌ 数据质量检查未通过")

        # 显示问题
        if report['issues']:
            print("\n🔴 严重问题:")
            for issue in report['issues'][:10]:  # 最多显示10个
                print(f"  - {issue}")
            if len(report['issues']) > 10:
                print(f"  ... 还有 {len(report['issues']) - 10} 个问题")

        # 显示警告
        if report['warnings']:
            print("\n🟡 警告:")
            for warning in report['warnings'][:10]:
                print(f"  - {warning}")
            if len(report['warnings']) > 10:
                print(f"  ... 还有 {len(report['warnings']) - 10} 个警告")

        # 显示股票统计
        if report['stock_reports']:
            print(f"\n📊 股票质量统计:")
            passed_count = sum(1 for r in report['stock_reports'].values() if not r['issues'])
            warning_count = sum(1 for r in report['stock_reports'].values() if r['warnings'] and not r['issues'])
            failed_count = sum(1 for r in report['stock_reports'].values() if r['issues'])

            print(f"  通过: {passed_count}")
            print(f"  警告: {warning_count}")
            print(f"  失败: {failed_count}")

        print("\n" + "=" * 70)

    def generate_quality_summary(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成数据质量汇总表

        参数:
            data: 数据

        返回:
            汇总DataFrame
        """
        summary = []

        for code in data['code'].unique():
            stock_data = data[data['code'] == code].sort_values('date')

            missing_pct = stock_data[['close', 'volume']].isnull().sum().sum() / (len(stock_data) * 2)
            price_changes = stock_data['close'].pct_change()
            extreme_changes = (price_changes.abs() > self.max_price_change_pct).sum()

            summary.append({
                'code': code,
                'records': len(stock_data),
                'missing_pct': missing_pct * 100,
                'extreme_changes': extreme_changes,
                'avg_volume': stock_data['volume'].mean(),
                'volatility': price_changes.std() * 100,
                'quality_score': self._calculate_quality_score(stock_data)
            })

        summary_df = pd.DataFrame(summary)
        summary_df = summary_df.sort_values('quality_score', ascending=False)
        return summary_df

    def _calculate_quality_score(self, stock_data: pd.DataFrame) -> float:
        """
        计算单个股票的数据质量得分（0-100）

        参数:
            stock_data: 股票数据

        返回:
            质量得分
        """
        score = 100

        # 数据量得分（满分30分）
        data_score = min(len(stock_data) / self.min_data_days, 1) * 30
        score = data_score

        # 缺失值得分（满分30分）
        missing_pct = stock_data[['close', 'volume']].isnull().sum().sum() / (len(stock_data) * 2)
        missing_score = max(0, (1 - missing_pct / self.max_missing_pct)) * 30
        score += missing_score

        # 异常值得分（满分20分）
        price_changes = stock_data['close'].pct_change()
        extreme_pct = (price_changes.abs() > self.max_price_change_pct).sum() / len(stock_data)
        extreme_score = max(0, (1 - extreme_pct * 10)) * 20
        score += extreme_score

        # 数据一致性得分（满分20分）
        # 检查OHLC逻辑
        invalid_ohlc = (
            (stock_data['high'] < stock_data['low']) |
            (stock_data['high'] < stock_data['close']) |
            (stock_data['low'] > stock_data['close'])
        ).sum()
        consistency_score = max(0, (1 - invalid_ohlc / len(stock_data))) * 20
        score += consistency_score

        return min(100, max(0, score))


def main():
    """测试数据质量检查器"""
    print("测试数据质量检查器...")

    # 生成测试数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

    data = []
    for code in ['SH600000', 'SH600036', 'SH600519']:
        for date in dates:
            price = np.random.uniform(10, 100)
            data.append({
                'code': code,
                'date': date.strftime('%Y-%m-%d'),
                'open': price * (1 + np.random.uniform(-0.02, 0.02)),
                'high': price * (1 + np.random.uniform(0, 0.03)),
                'low': price * (1 - np.random.uniform(0, 0.03)),
                'close': price,
                'volume': np.random.uniform(1e6, 1e8)
            })

    df = pd.DataFrame(data)

    # 故意添加一些问题
    df.loc[0, 'close'] = -10  # 无效价格
    df.loc[10, 'volume'] = np.nan  # 缺失值
    df.loc[20, 'close'] = df.loc[19, 'close'] * 1.5  # 异常涨幅

    # 创建检查器
    checker = DataQualityChecker()

    # 检查数据
    report = checker.check_data(df)

    # 打印报告
    checker.print_report(report)

    # 清洗数据
    print("\n--- 清洗数据 ---")
    cleaned_df = checker.clean_data(df)

    # 再次检查
    print("\n--- 清洗后重新检查 ---")
    report_after = checker.check_data(cleaned_df)
    checker.print_report(report_after)

    # 质量汇总
    print("\n--- 质量汇总 ---")
    summary = checker.generate_quality_summary(cleaned_df)
    print(summary)

    print("\n✅ 数据质量检查器测试完成")


if __name__ == '__main__':
    main()
