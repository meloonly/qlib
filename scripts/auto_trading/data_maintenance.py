#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据维护模块

功能：
1. 增量数据更新 - 只更新缺失的日期，避免重复下载
2. 数据完整性校验 - 检查数据质量和连续性
3. 自动修复异常 - 修复缺失值、异常值
4. 历史数据归档 - 定期清理和压缩旧数据
5. 数据统计报告 - 生成数据质量报告

使用方法:
    from data_maintenance import DataMaintenance

    dm = DataMaintenance()

    # 增量更新数据
    dm.incremental_update(['600000', '000001'])

    # 检查数据完整性
    report = dm.check_data_integrity()

    # 修复异常数据
    dm.fix_data_issues()

    # 归档历史数据
    dm.archive_old_data(days=1095)  # 归档3年前的数据
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import gzip
import shutil
from typing import List, Dict, Tuple
import warnings

warnings.filterwarnings('ignore')


class DataMaintenance:
    """数据维护和自动更新"""

    def __init__(self, data_dir: str = "./data", cache_dir: str = "./data/akshare_cache"):
        """
        初始化数据维护模块

        Args:
            data_dir: 数据目录
            cache_dir: AKShare缓存目录
        """
        self.data_dir = Path(data_dir)
        self.cache_dir = Path(cache_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 元数据文件
        self.metadata_file = self.data_dir / "data_metadata.json"
        self.metadata = self._load_metadata()

        # 初始化数据获取器
        self._init_fetcher()

    def _init_fetcher(self):
        """初始化AKShare数据获取器"""
        try:
            from akshare_fetcher import AKShareDataFetcher
            self.fetcher = AKShareDataFetcher(cache_dir=str(self.cache_dir))
            print("✅ 数据获取器初始化成功 (AKShare)")
        except ImportError:
            print("⚠️ AKShare未安装，尝试使用Yahoo Finance")
            try:
                from real_data_fetcher import YahooFinanceDataFetcher
                self.fetcher = YahooFinanceDataFetcher()
                print("✅ 数据获取器初始化成功 (Yahoo Finance)")
            except:
                self.fetcher = None
                print("❌ 数据获取器初始化失败")

    def _load_metadata(self) -> dict:
        """加载元数据"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "stocks": {},  # {code: {"last_update": "2025-01-01", "total_records": 1000}}
            "last_check": None,
            "issues": [],
            "archives": []
        }

    def _save_metadata(self):
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def get_stock_file_path(self, code: str) -> Path:
        """获取股票数据文件路径"""
        return self.cache_dir / f"{code}.csv"

    def get_last_update_date(self, code: str) -> str:
        """获取股票最后更新日期"""
        if code in self.metadata["stocks"]:
            return self.metadata["stocks"][code]["last_update"]

        # 如果元数据没有，尝试从文件读取
        file_path = self.get_stock_file_path(code)
        if file_path.exists():
            df = pd.read_csv(file_path)
            if not df.empty and 'date' in df.columns:
                return df['date'].max()

        return None

    def incremental_update(self, codes: List[str], source: str = "akshare") -> Dict:
        """
        增量更新股票数据

        Args:
            codes: 股票代码列表
            source: 数据源 (akshare/yahoo/tushare)

        Returns:
            更新统计信息
        """
        print(f"\n🔄 开始增量数据更新 ({len(codes)} 只股票)")
        print(f"数据源: {source}")
        print("=" * 60)

        stats = {
            "total": len(codes),
            "updated": 0,
            "new": 0,
            "failed": 0,
            "skipped": 0,
            "total_records": 0
        }

        for i, code in enumerate(codes, 1):
            print(f"\n[{i}/{len(codes)}] 处理 {code}")

            try:
                # 获取最后更新日期
                last_date = self.get_last_update_date(code)

                if last_date:
                    # 增量更新：只获取最后更新日期之后的数据
                    last_dt = datetime.strptime(last_date, '%Y-%m-%d')

                    # 如果已经是最新（考虑周末和节假日，留3天缓冲）
                    if (datetime.now() - last_dt).days <= 3:
                        print(f"  ℹ️ 数据已是最新 (最后更新: {last_date})")
                        stats["skipped"] += 1
                        continue

                    start_date = (last_dt + timedelta(days=1)).strftime('%Y-%m-%d')
                    end_date = datetime.now().strftime('%Y-%m-%d')

                    print(f"  📥 增量更新: {start_date} ~ {end_date}")

                    # 获取新数据
                    new_data = self._fetch_data(code, start_date, end_date, source)

                    if new_data.empty:
                        print(f"  ✅ 无新数据需要更新")
                        stats["skipped"] += 1
                        continue

                    # 加载旧数据
                    file_path = self.get_stock_file_path(code)
                    old_data = pd.read_csv(file_path)

                    # 合并数据
                    combined = pd.concat([old_data, new_data], ignore_index=True)
                    combined = combined.drop_duplicates(subset=['date'], keep='last')
                    combined = combined.sort_values('date').reset_index(drop=True)

                    # 保存
                    combined.to_csv(file_path, index=False, encoding='utf-8-sig')

                    print(f"  ✅ 更新成功: 新增 {len(new_data)} 条记录，总计 {len(combined)} 条")
                    stats["updated"] += 1
                    stats["total_records"] += len(new_data)

                else:
                    # 全量下载：首次获取数据
                    print(f"  📥 首次下载完整数据")
                    days = 365  # 默认获取1年数据

                    data = self._fetch_data(code, days=days, source=source)

                    if data.empty:
                        print(f"  ❌ 获取数据失败")
                        stats["failed"] += 1
                        continue

                    # 保存
                    file_path = self.get_stock_file_path(code)
                    data.to_csv(file_path, index=False, encoding='utf-8-sig')

                    print(f"  ✅ 下载成功: {len(data)} 条记录")
                    stats["new"] += 1
                    stats["total_records"] += len(data)

                # 更新元数据
                df = pd.read_csv(self.get_stock_file_path(code))
                self.metadata["stocks"][code] = {
                    "last_update": df['date'].max(),
                    "total_records": len(df),
                    "first_date": df['date'].min(),
                    "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            except Exception as e:
                print(f"  ❌ 更新失败: {str(e)}")
                stats["failed"] += 1
                self.metadata["issues"].append({
                    "code": code,
                    "error": str(e),
                    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })

        # 保存元数据
        self._save_metadata()

        # 打印统计
        print("\n" + "=" * 60)
        print("📊 更新统计:")
        print(f"  总数: {stats['total']}")
        print(f"  新增: {stats['new']}")
        print(f"  更新: {stats['updated']}")
        print(f"  跳过: {stats['skipped']}")
        print(f"  失败: {stats['failed']}")
        print(f"  新增记录数: {stats['total_records']}")

        return stats

    def _fetch_data(self, code: str, start_date: str = None, end_date: str = None,
                    days: int = None, source: str = "akshare") -> pd.DataFrame:
        """获取数据的内部方法"""
        if self.fetcher is None:
            return pd.DataFrame()

        try:
            if hasattr(self.fetcher, 'fetch_stock_history'):
                # AKShare
                return self.fetcher.fetch_stock_history(
                    code=code,
                    start_date=start_date,
                    end_date=end_date,
                    days=days or 365
                )
            else:
                # Yahoo Finance
                if start_date is None and days:
                    end_date = datetime.now().strftime('%Y-%m-%d')
                    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

                return self.fetcher.fetch_single_stock(code, start_date, end_date)
        except Exception as e:
            print(f"  ⚠️ 数据获取异常: {str(e)[:100]}")
            return pd.DataFrame()

    def check_data_integrity(self, codes: List[str] = None) -> Dict:
        """
        检查数据完整性

        Returns:
            检查报告
        """
        print("\n🔍 检查数据完整性...")

        if codes is None:
            codes = list(self.metadata["stocks"].keys())

        report = {
            "check_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_stocks": len(codes),
            "issues": [],
            "summary": {
                "missing_dates": 0,
                "duplicate_dates": 0,
                "zero_volume": 0,
                "price_anomaly": 0,
                "outdated": 0
            }
        }

        for code in codes:
            file_path = self.get_stock_file_path(code)

            if not file_path.exists():
                report["issues"].append({
                    "code": code,
                    "type": "file_not_found",
                    "severity": "high"
                })
                continue

            df = pd.read_csv(file_path)

            if df.empty:
                report["issues"].append({
                    "code": code,
                    "type": "empty_file",
                    "severity": "high"
                })
                continue

            # 检查1: 日期连续性
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            date_diff = df['date'].diff().dt.days

            # 找出缺失的交易日（间隔>5天视为异常，考虑周末和节假日）
            missing = date_diff[date_diff > 5]
            if len(missing) > 0:
                report["issues"].append({
                    "code": code,
                    "type": "missing_dates",
                    "count": len(missing),
                    "severity": "medium"
                })
                report["summary"]["missing_dates"] += len(missing)

            # 检查2: 重复日期
            duplicates = df[df.duplicated(subset=['date'], keep=False)]
            if len(duplicates) > 0:
                report["issues"].append({
                    "code": code,
                    "type": "duplicate_dates",
                    "count": len(duplicates),
                    "severity": "high"
                })
                report["summary"]["duplicate_dates"] += len(duplicates)

            # 检查3: 成交量为0
            zero_vol = df[df['volume'] == 0]
            if len(zero_vol) > len(df) * 0.1:  # 超过10%的记录成交量为0
                report["issues"].append({
                    "code": code,
                    "type": "zero_volume",
                    "count": len(zero_vol),
                    "severity": "low"
                })
                report["summary"]["zero_volume"] += len(zero_vol)

            # 检查4: 价格异常（单日涨跌幅>50%）
            df['pct_change'] = df['close'].pct_change()
            anomalies = df[abs(df['pct_change']) > 0.5]
            if len(anomalies) > 0:
                report["issues"].append({
                    "code": code,
                    "type": "price_anomaly",
                    "count": len(anomalies),
                    "dates": anomalies['date'].dt.strftime('%Y-%m-%d').tolist()[:5],
                    "severity": "medium"
                })
                report["summary"]["price_anomaly"] += len(anomalies)

            # 检查5: 数据是否过时（超过7天未更新）
            last_date = df['date'].max()
            days_old = (datetime.now() - last_date).days

            if days_old > 7:
                report["issues"].append({
                    "code": code,
                    "type": "outdated",
                    "last_date": last_date.strftime('%Y-%m-%d'),
                    "days_old": days_old,
                    "severity": "high"
                })
                report["summary"]["outdated"] += 1

        # 打印报告摘要
        print(f"\n检查完成: {len(codes)} 只股票")
        print(f"发现问题: {len(report['issues'])} 个")
        if report["summary"]["outdated"] > 0:
            print(f"  ⚠️ 数据过时: {report['summary']['outdated']} 只")
        if report["summary"]["missing_dates"] > 0:
            print(f"  ⚠️ 日期缺失: {report['summary']['missing_dates']} 处")
        if report["summary"]["duplicate_dates"] > 0:
            print(f"  ⚠️ 重复日期: {report['summary']['duplicate_dates']} 处")

        return report

    def fix_data_issues(self, codes: List[str] = None) -> Dict:
        """
        自动修复数据问题

        Returns:
            修复统计
        """
        print("\n🔧 自动修复数据问题...")

        if codes is None:
            codes = list(self.metadata["stocks"].keys())

        stats = {
            "processed": 0,
            "fixed_duplicates": 0,
            "fixed_zeros": 0,
            "fixed_anomalies": 0
        }

        for code in codes:
            file_path = self.get_stock_file_path(code)

            if not file_path.exists():
                continue

            df = pd.read_csv(file_path)

            if df.empty:
                continue

            original_len = len(df)

            # 修复1: 删除重复日期（保留最新）
            before = len(df)
            df = df.drop_duplicates(subset=['date'], keep='last')
            if len(df) < before:
                stats["fixed_duplicates"] += (before - len(df))
                print(f"  {code}: 删除 {before - len(df)} 条重复记录")

            # 修复2: 填充缺失值
            if df[['open', 'high', 'low', 'close']].isnull().any().any():
                df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].fillna(method='ffill')
                print(f"  {code}: 填充价格缺失值")

            # 修复3: 修正异常的成交量为0（用前后平均值填充）
            zero_vol_idx = df[df['volume'] == 0].index
            if len(zero_vol_idx) > 0:
                df.loc[zero_vol_idx, 'volume'] = df['volume'].replace(0, np.nan).fillna(method='ffill').fillna(method='bfill')
                stats["fixed_zeros"] += len(zero_vol_idx)
                print(f"  {code}: 修复 {len(zero_vol_idx)} 条零成交量")

            # 保存修复后的数据
            if len(df) != original_len or stats["fixed_zeros"] > 0:
                df = df.sort_values('date').reset_index(drop=True)
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
                stats["processed"] += 1

        print(f"\n✅ 修复完成:")
        print(f"  处理文件: {stats['processed']}")
        print(f"  删除重复: {stats['fixed_duplicates']}")
        print(f"  修复零值: {stats['fixed_zeros']}")

        return stats

    def archive_old_data(self, days: int = 1095) -> Dict:
        """
        归档旧数据（压缩3年前的数据）

        Args:
            days: 保留最近N天的数据，更早的归档

        Returns:
            归档统计
        """
        print(f"\n📦 归档 {days} 天前的数据...")

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        archive_dir = self.data_dir / "archives"
        archive_dir.mkdir(exist_ok=True)

        stats = {
            "processed": 0,
            "archived_records": 0,
            "saved_space": 0
        }

        for code in self.metadata["stocks"].keys():
            file_path = self.get_stock_file_path(code)

            if not file_path.exists():
                continue

            df = pd.read_csv(file_path)

            if df.empty:
                continue

            # 分离新旧数据
            df['date'] = pd.to_datetime(df['date'])
            old_data = df[df['date'] < cutoff_date]
            new_data = df[df['date'] >= cutoff_date]

            if len(old_data) == 0:
                continue

            # 归档旧数据（压缩）
            archive_file = archive_dir / f"{code}_archive_{datetime.now().strftime('%Y%m%d')}.csv.gz"
            old_data.to_csv(archive_file, index=False, encoding='utf-8-sig', compression='gzip')

            # 只保留新数据
            new_data.to_csv(file_path, index=False, encoding='utf-8-sig')

            original_size = file_path.stat().st_size
            new_size = file_path.stat().st_size

            stats["processed"] += 1
            stats["archived_records"] += len(old_data)
            stats["saved_space"] += (original_size - new_size)

            print(f"  {code}: 归档 {len(old_data)} 条记录")

        print(f"\n✅ 归档完成:")
        print(f"  处理股票: {stats['processed']}")
        print(f"  归档记录: {stats['archived_records']}")
        print(f"  节省空间: {stats['saved_space'] / 1024 / 1024:.2f} MB")

        # 更新元数据
        self.metadata["archives"].append({
            "date": datetime.now().strftime('%Y-%m-%d'),
            "cutoff_date": cutoff_date,
            "archived_stocks": stats["processed"],
            "archived_records": stats["archived_records"]
        })
        self._save_metadata()

        return stats

    def generate_report(self) -> str:
        """生成数据质量报告"""
        report = []
        report.append("=" * 60)
        report.append("📊 数据维护报告")
        report.append("=" * 60)
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 统计信息
        total_stocks = len(self.metadata["stocks"])
        report.append(f"\n总股票数: {total_stocks}")

        if total_stocks > 0:
            total_records = sum(s["total_records"] for s in self.metadata["stocks"].values())
            report.append(f"总记录数: {total_records:,}")

            # 最近更新时间
            latest_updates = sorted(
                [(code, info["last_update"]) for code, info in self.metadata["stocks"].items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]

            report.append("\n最近更新的股票:")
            for code, date in latest_updates:
                report.append(f"  {code}: {date}")

            # 过时数据
            outdated = []
            for code, info in self.metadata["stocks"].items():
                last_date = datetime.strptime(info["last_update"], '%Y-%m-%d')
                if (datetime.now() - last_date).days > 7:
                    outdated.append(code)

            if outdated:
                report.append(f"\n⚠️ 数据过时 ({len(outdated)} 只):")
                for code in outdated[:10]:
                    report.append(f"  {code}")

        # 问题列表
        if self.metadata["issues"]:
            report.append(f"\n⚠️ 最近问题 (最多显示10条):")
            for issue in self.metadata["issues"][-10:]:
                report.append(f"  {issue['code']}: {issue['error'][:50]} @ {issue['time']}")

        report.append("\n" + "=" * 60)

        return "\n".join(report)


if __name__ == "__main__":
    # 测试
    dm = DataMaintenance()

    # 增量更新
    test_codes = ['600000', '000001', '600036']
    dm.incremental_update(test_codes)

    # 检查完整性
    report = dm.check_data_integrity(test_codes)

    # 修复问题
    dm.fix_data_issues(test_codes)

    # 生成报告
    print(dm.generate_report())
