#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓管理系统 (Portfolio Management System)

功能：
- 持仓记录管理（添加、修改、删除）
- 自动价格更新
- 实时盈亏计算
- 风险提醒（止损/止盈）
- 仓位控制
- 交易历史记录
- 策略信号集成
- HTML报告生成
- 交互式菜单界面

使用方法:
    python portfolio_management.py
    # 进入交互式菜单
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# 添加路径
sys.path.append(str(Path(__file__).parent))


class PortfolioManager:
    """
    持仓管理器

    使用SQLite数据库存储持仓和交易记录
    """

    def __init__(self, db_path: str = None):
        """
        初始化持仓管理器

        参数:
            db_path: 数据库文件路径，默认为当前目录下的portfolio.db
        """
        if db_path is None:
            db_path = str(Path(__file__).parent / "portfolio.db")

        self.db_path = db_path
        self.conn = None
        self._init_database()

        # 风险控制参数
        self.stop_loss_threshold = -0.10  # 止损线：-10%
        self.take_profit_threshold = 0.20  # 止盈线：+20%
        self.max_single_position_pct = 0.20  # 单股最大仓位：20%
        self.min_cash_ratio = 0.05  # 最低现金比例：5%

    def _init_database(self):
        """初始化数据库表"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT,
                shares INTEGER NOT NULL,
                cost_price REAL NOT NULL,
                current_price REAL,
                buy_date TEXT NOT NULL,
                strategy TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                shares INTEGER NOT NULL,
                amount REAL NOT NULL,
                fee REAL DEFAULT 0,
                reason TEXT,
                strategy TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 账户信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                cash REAL NOT NULL DEFAULT 1000000,
                initial_capital REAL NOT NULL DEFAULT 1000000,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 初始化账户（如果不存在）
        cursor.execute('SELECT COUNT(*) FROM account')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO account (id, cash, initial_capital)
                VALUES (1, 1000000, 1000000)
            ''')

        # 风险提醒表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_date TEXT NOT NULL,
                code TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()
        print(f"✅ 数据库已初始化: {self.db_path}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    # ==================== 账户管理 ====================

    def get_account_info(self) -> dict:
        """获取账户信息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT cash, initial_capital, updated_at FROM account WHERE id = 1')
        row = cursor.fetchone()

        if row:
            cash, initial_capital, updated_at = row
            positions_value = self._calculate_positions_value()
            total_value = cash + positions_value
            total_pnl = total_value - initial_capital
            total_pnl_pct = total_pnl / initial_capital * 100

            return {
                'cash': cash,
                'initial_capital': initial_capital,
                'positions_value': positions_value,
                'total_value': total_value,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'updated_at': updated_at
            }
        return {}

    def set_initial_capital(self, amount: float):
        """设置初始资金"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE account SET cash = ?, initial_capital = ?, updated_at = ?
            WHERE id = 1
        ''', (amount, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.conn.commit()
        print(f"✅ 初始资金已设置为: ¥{amount:,.2f}")

    def _update_cash(self, amount: float):
        """更新现金余额"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT cash FROM account WHERE id = 1')
        current_cash = cursor.fetchone()[0]
        new_cash = current_cash + amount

        cursor.execute('''
            UPDATE account SET cash = ?, updated_at = ?
            WHERE id = 1
        ''', (new_cash, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.conn.commit()

    def _calculate_positions_value(self) -> float:
        """计算持仓总市值"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT shares, current_price, cost_price FROM positions')
        total_value = 0
        for shares, current_price, cost_price in cursor.fetchall():
            price = current_price if current_price else cost_price
            total_value += shares * price
        return total_value

    # ==================== 持仓管理 ====================

    def add_position(self, code: str, shares: int, price: float,
                    name: str = None, strategy: str = None, notes: str = None,
                    date: str = None) -> bool:
        """
        添加持仓（买入）

        参数:
            code: 股票代码
            shares: 股数
            price: 买入价格
            name: 股票名称（可选）
            strategy: 使用的策略（可选）
            notes: 备注（可选）
            date: 买入日期（可选，默认今天）

        返回:
            是否成功
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # 计算所需资金
        amount = shares * price
        fee = amount * 0.0003  # 假设手续费0.03%
        total_cost = amount + fee

        # 检查资金是否充足
        account = self.get_account_info()
        if total_cost > account['cash']:
            print(f"❌ 资金不足！需要¥{total_cost:,.2f}，现有¥{account['cash']:,.2f}")
            return False

        # 检查单股仓位限制
        new_total_value = account['total_value']
        new_position_pct = amount / new_total_value
        if new_position_pct > self.max_single_position_pct:
            print(f"⚠️ 警告：此次买入将使该股票仓位达到 {new_position_pct*100:.1f}%，超过限制 {self.max_single_position_pct*100:.0f}%")

        cursor = self.conn.cursor()

        # 检查是否已有该股票持仓
        cursor.execute('SELECT id, shares, cost_price FROM positions WHERE code = ?', (code,))
        existing = cursor.fetchone()

        if existing:
            # 加仓：计算平均成本
            old_id, old_shares, old_cost = existing
            new_shares = old_shares + shares
            new_cost = (old_shares * old_cost + shares * price) / new_shares

            cursor.execute('''
                UPDATE positions SET shares = ?, cost_price = ?, updated_at = ?
                WHERE id = ?
            ''', (new_shares, new_cost, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), old_id))
            print(f"✅ 加仓成功: {code}, 新增{shares}股@¥{price:.2f}, 总持仓{new_shares}股, 平均成本¥{new_cost:.2f}")
        else:
            # 新建仓位
            cursor.execute('''
                INSERT INTO positions (code, name, shares, cost_price, current_price, buy_date, strategy, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, name, shares, price, price, date, strategy, notes))
            print(f"✅ 建仓成功: {code}, {shares}股@¥{price:.2f}")

        # 记录交易
        cursor.execute('''
            INSERT INTO trades (trade_date, code, name, action, price, shares, amount, fee, reason, strategy)
            VALUES (?, ?, ?, 'buy', ?, ?, ?, ?, ?, ?)
        ''', (date, code, name, price, shares, amount, fee, notes, strategy))

        # 扣除资金
        self._update_cash(-total_cost)

        self.conn.commit()
        return True

    def sell_position(self, code: str, shares: int, price: float,
                     reason: str = None, date: str = None) -> bool:
        """
        卖出持仓

        参数:
            code: 股票代码
            shares: 卖出股数
            price: 卖出价格
            reason: 卖出原因（可选）
            date: 卖出日期（可选，默认今天）

        返回:
            是否成功
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        cursor = self.conn.cursor()

        # 检查持仓是否存在
        cursor.execute('SELECT id, shares, cost_price, name, strategy FROM positions WHERE code = ?', (code,))
        existing = cursor.fetchone()

        if not existing:
            print(f"❌ 未找到 {code} 的持仓")
            return False

        position_id, current_shares, cost_price, name, strategy = existing

        if shares > current_shares:
            print(f"❌ 持仓不足！当前持有{current_shares}股，无法卖出{shares}股")
            return False

        # 计算卖出金额
        amount = shares * price
        fee = amount * 0.0013  # 假设卖出手续费0.13%（含印花税）
        net_amount = amount - fee

        # 计算盈亏
        cost = shares * cost_price
        profit = net_amount - cost
        profit_pct = profit / cost * 100

        # 更新持仓
        if shares == current_shares:
            # 清仓
            cursor.execute('DELETE FROM positions WHERE id = ?', (position_id,))
            print(f"✅ 清仓: {code}, 卖出{shares}股@¥{price:.2f}, 盈亏: ¥{profit:,.2f} ({profit_pct:+.2f}%)")
        else:
            # 部分卖出
            new_shares = current_shares - shares
            cursor.execute('''
                UPDATE positions SET shares = ?, updated_at = ?
                WHERE id = ?
            ''', (new_shares, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), position_id))
            print(f"✅ 减仓: {code}, 卖出{shares}股@¥{price:.2f}, 剩余{new_shares}股, 盈亏: ¥{profit:,.2f} ({profit_pct:+.2f}%)")

        # 记录交易
        cursor.execute('''
            INSERT INTO trades (trade_date, code, name, action, price, shares, amount, fee, reason, strategy)
            VALUES (?, ?, ?, 'sell', ?, ?, ?, ?, ?, ?)
        ''', (date, code, name, price, shares, amount, fee, reason, strategy))

        # 增加资金
        self._update_cash(net_amount)

        self.conn.commit()
        return True

    def get_all_positions(self) -> pd.DataFrame:
        """获取所有持仓"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT code, name, shares, cost_price, current_price, buy_date, strategy, notes
            FROM positions ORDER BY code
        ''')

        data = []
        for row in cursor.fetchall():
            code, name, shares, cost_price, current_price, buy_date, strategy, notes = row

            # 使用当前价格计算盈亏（如果没有当前价格，使用成本价）
            price = current_price if current_price else cost_price
            market_value = shares * price
            cost_value = shares * cost_price
            profit_loss = market_value - cost_value
            profit_pct = profit_loss / cost_value * 100 if cost_value > 0 else 0

            data.append({
                'code': code,
                'name': name or '',
                'shares': shares,
                'cost_price': cost_price,
                'current_price': price,
                'market_value': market_value,
                'cost_value': cost_value,
                'profit_loss': profit_loss,
                'profit_pct': profit_pct,
                'buy_date': buy_date,
                'strategy': strategy or '',
                'notes': notes or ''
            })

        return pd.DataFrame(data)

    def update_prices(self, prices: dict):
        """
        更新持仓的当前价格

        参数:
            prices: {code: price} 字典
        """
        cursor = self.conn.cursor()
        updated_count = 0

        for code, price in prices.items():
            cursor.execute('''
                UPDATE positions SET current_price = ?, updated_at = ?
                WHERE code = ?
            ''', (price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), code))

            if cursor.rowcount > 0:
                updated_count += 1

        self.conn.commit()
        print(f"✅ 已更新 {updated_count} 个持仓的价格")

        # 检查风险提醒
        self._check_risk_alerts()

    def _check_risk_alerts(self):
        """检查风险提醒"""
        positions = self.get_all_positions()
        cursor = self.conn.cursor()

        for _, pos in positions.iterrows():
            code = pos['code']
            profit_pct = pos['profit_pct'] / 100

            # 检查止损
            if profit_pct <= self.stop_loss_threshold:
                message = f"⚠️ 止损提醒: {code} 已亏损 {profit_pct*100:.2f}%，达到止损线 {self.stop_loss_threshold*100:.0f}%"
                cursor.execute('''
                    INSERT INTO alerts (alert_date, code, alert_type, message)
                    VALUES (?, ?, 'stop_loss', ?)
                ''', (datetime.now().strftime('%Y-%m-%d'), code, message))
                print(message)

            # 检查止盈
            elif profit_pct >= self.take_profit_threshold:
                message = f"🎯 止盈提醒: {code} 已盈利 {profit_pct*100:.2f}%，达到止盈线 {self.take_profit_threshold*100:.0f}%"
                cursor.execute('''
                    INSERT INTO alerts (alert_date, code, alert_type, message)
                    VALUES (?, ?, 'take_profit', ?)
                ''', (datetime.now().strftime('%Y-%m-%d'), code, message))
                print(message)

        self.conn.commit()

    # ==================== 交易历史 ====================

    def get_trade_history(self, code: str = None, limit: int = 50) -> pd.DataFrame:
        """
        获取交易历史

        参数:
            code: 股票代码（可选，不指定则返回所有）
            limit: 返回记录数量限制

        返回:
            交易记录DataFrame
        """
        cursor = self.conn.cursor()

        if code:
            cursor.execute('''
                SELECT trade_date, code, name, action, price, shares, amount, fee, reason, strategy
                FROM trades WHERE code = ? ORDER BY trade_date DESC, id DESC LIMIT ?
            ''', (code, limit))
        else:
            cursor.execute('''
                SELECT trade_date, code, name, action, price, shares, amount, fee, reason, strategy
                FROM trades ORDER BY trade_date DESC, id DESC LIMIT ?
            ''', (limit,))

        columns = ['date', 'code', 'name', 'action', 'price', 'shares', 'amount', 'fee', 'reason', 'strategy']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

    # ==================== 业绩分析 ====================

    def get_performance_summary(self) -> dict:
        """获取业绩汇总"""
        account = self.get_account_info()
        positions = self.get_all_positions()
        trades = self.get_trade_history(limit=1000)

        # 计算持仓分布
        total_value = account['total_value']
        position_weights = {}
        for _, pos in positions.iterrows():
            code = pos['code']
            weight = pos['market_value'] / total_value * 100
            position_weights[code] = weight

        # 计算交易统计
        total_trades = len(trades)
        buy_trades = len(trades[trades['action'] == 'buy'])
        sell_trades = len(trades[trades['action'] == 'sell'])

        # 计算已实现盈亏（从卖出交易中）
        realized_pnl = 0
        # 简化计算：这里只统计交易费用
        total_fees = trades['fee'].sum()

        return {
            'account': account,
            'positions_count': len(positions),
            'position_weights': position_weights,
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'total_fees': total_fees,
            'cash_ratio': account['cash'] / total_value * 100 if total_value > 0 else 100
        }

    def get_alerts(self, unread_only: bool = True) -> pd.DataFrame:
        """获取风险提醒"""
        cursor = self.conn.cursor()

        if unread_only:
            cursor.execute('''
                SELECT alert_date, code, alert_type, message, created_at
                FROM alerts WHERE is_read = 0 ORDER BY created_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT alert_date, code, alert_type, message, created_at
                FROM alerts ORDER BY created_at DESC LIMIT 50
            ''')

        columns = ['date', 'code', 'type', 'message', 'created_at']
        return pd.DataFrame(cursor.fetchall(), columns=columns)

    def mark_alerts_read(self):
        """标记所有提醒为已读"""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE alerts SET is_read = 1')
        self.conn.commit()
        print("✅ 所有提醒已标记为已读")

    # ==================== 策略信号集成 ====================

    def apply_signals(self, signals: pd.DataFrame, auto_execute: bool = False):
        """
        应用策略信号

        参数:
            signals: DataFrame with columns ['code', 'signal', 'score']
                    signal: 1 (买入), -1 (卖出), 0 (持有)
            auto_execute: 是否自动执行交易

        返回:
            建议的操作列表
        """
        positions = self.get_all_positions()
        account = self.get_account_info()

        recommendations = []

        # 处理卖出信号
        for _, pos in positions.iterrows():
            code = pos['code']
            signal_row = signals[signals['code'] == code]

            if not signal_row.empty:
                signal = signal_row.iloc[0]['signal']
                if signal == -1:  # 卖出信号
                    recommendations.append({
                        'action': 'sell',
                        'code': code,
                        'shares': pos['shares'],
                        'reason': '策略卖出信号',
                        'current_price': pos['current_price'],
                        'profit_pct': pos['profit_pct']
                    })

        # 处理买入信号
        buy_signals = signals[signals['signal'] == 1].sort_values('score', ascending=False)
        available_cash = account['cash'] * (1 - self.min_cash_ratio)

        for _, sig in buy_signals.head(5).iterrows():  # 最多推荐5个
            code = sig['code']
            if code not in positions['code'].values:
                recommendations.append({
                    'action': 'buy',
                    'code': code,
                    'score': sig['score'],
                    'reason': '策略买入信号',
                    'max_amount': available_cash / 5  # 平均分配
                })

        print("\n📋 策略信号分析结果:")
        print("=" * 60)

        if not recommendations:
            print("无交易建议")
        else:
            for rec in recommendations:
                if rec['action'] == 'sell':
                    print(f"🔴 卖出: {rec['code']}, {rec['shares']}股, 盈亏{rec['profit_pct']:+.2f}%")
                else:
                    print(f"🟢 买入: {rec['code']}, 评分{rec['score']:.1f}, 建议金额≤¥{rec['max_amount']:,.0f}")

        if auto_execute:
            print("\n⚠️ 自动执行模式暂未启用，请手动确认交易")

        return recommendations

    # ==================== 报告生成 ====================

    def generate_html_report(self, output_file: str = None) -> str:
        """
        生成HTML格式的持仓报告

        参数:
            output_file: 输出文件路径

        返回:
            HTML内容
        """
        if output_file is None:
            output_file = str(Path(__file__).parent / "reports" / f"portfolio_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

        # 创建目录
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # 获取数据
        account = self.get_account_info()
        positions = self.get_all_positions()
        summary = self.get_performance_summary()
        trades = self.get_trade_history(limit=20)
        alerts = self.get_alerts(unread_only=False)

        # 生成HTML
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>持仓管理报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: right; border-bottom: 1px solid #ddd; }}
        th {{ background: #3498db; color: white; text-align: center; }}
        td:first-child {{ text-align: left; }}
        tr:nth-child(even) {{ background: #f2f2f2; }}
        tr:hover {{ background: #e8f4f8; }}
        .positive {{ color: #27ae60; font-weight: bold; }}
        .negative {{ color: #e74c3c; font-weight: bold; }}
        .summary-box {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 10px 0; display: inline-block; margin-right: 20px; }}
        .summary-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .alert-box {{ background: #ffeaa7; padding: 10px; border-radius: 5px; margin: 5px 0; }}
        .timestamp {{ color: #7f8c8d; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 持仓管理报告</h1>
        <p class="timestamp">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>💰 账户概览</h2>
        <div>
            <div class="summary-box">
                <div>总资产</div>
                <div class="summary-value">¥{account['total_value']:,.2f}</div>
            </div>
            <div class="summary-box">
                <div>现金</div>
                <div class="summary-value">¥{account['cash']:,.2f}</div>
            </div>
            <div class="summary-box">
                <div>持仓市值</div>
                <div class="summary-value">¥{account['positions_value']:,.2f}</div>
            </div>
            <div class="summary-box">
                <div>总盈亏</div>
                <div class="summary-value {'positive' if account['total_pnl'] >= 0 else 'negative'}">
                    ¥{account['total_pnl']:,.2f} ({account['total_pnl_pct']:+.2f}%)
                </div>
            </div>
        </div>

        <h2>📈 当前持仓</h2>
'''

        if positions.empty:
            html_content += '<p>暂无持仓</p>'
        else:
            html_content += '''
        <table>
            <tr>
                <th>代码</th>
                <th>名称</th>
                <th>股数</th>
                <th>成本价</th>
                <th>当前价</th>
                <th>市值</th>
                <th>盈亏</th>
                <th>盈亏%</th>
                <th>买入日期</th>
                <th>策略</th>
            </tr>
'''
            for _, pos in positions.iterrows():
                pnl_class = 'positive' if pos['profit_loss'] >= 0 else 'negative'
                html_content += f'''
            <tr>
                <td>{pos['code']}</td>
                <td>{pos['name']}</td>
                <td>{pos['shares']:,}</td>
                <td>¥{pos['cost_price']:.2f}</td>
                <td>¥{pos['current_price']:.2f}</td>
                <td>¥{pos['market_value']:,.2f}</td>
                <td class="{pnl_class}">¥{pos['profit_loss']:,.2f}</td>
                <td class="{pnl_class}">{pos['profit_pct']:+.2f}%</td>
                <td>{pos['buy_date']}</td>
                <td>{pos['strategy']}</td>
            </tr>
'''
            html_content += '</table>'

        # 最近交易
        html_content += '<h2>📝 最近交易</h2>'
        if trades.empty:
            html_content += '<p>暂无交易记录</p>'
        else:
            html_content += '''
        <table>
            <tr>
                <th>日期</th>
                <th>代码</th>
                <th>操作</th>
                <th>价格</th>
                <th>股数</th>
                <th>金额</th>
                <th>原因</th>
            </tr>
'''
            for _, trade in trades.head(10).iterrows():
                action_text = '买入' if trade['action'] == 'buy' else '卖出'
                action_color = 'negative' if trade['action'] == 'buy' else 'positive'
                html_content += f'''
            <tr>
                <td>{trade['date']}</td>
                <td>{trade['code']}</td>
                <td class="{action_color}">{action_text}</td>
                <td>¥{trade['price']:.2f}</td>
                <td>{trade['shares']:,}</td>
                <td>¥{trade['amount']:,.2f}</td>
                <td>{trade['reason'] or ''}</td>
            </tr>
'''
            html_content += '</table>'

        # 风险提醒
        if not alerts.empty:
            html_content += '<h2>⚠️ 风险提醒</h2>'
            for _, alert in alerts.head(5).iterrows():
                html_content += f'<div class="alert-box">{alert["message"]}</div>'

        html_content += '''
    </div>
</body>
</html>
'''

        # 保存文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ 报告已生成: {output_file}")
        return html_content


# ==================== 交互式菜单 ====================

def interactive_menu():
    """交互式菜单主函数"""
    pm = PortfolioManager()

    while True:
        print("\n" + "=" * 60)
        print("📊 持仓管理系统")
        print("=" * 60)
        print("1. 查看账户概览")
        print("2. 查看当前持仓")
        print("3. 买入股票")
        print("4. 卖出股票")
        print("5. 更新股票价格")
        print("6. 查看交易历史")
        print("7. 查看风险提醒")
        print("8. 生成HTML报告")
        print("9. 设置初始资金")
        print("10. 业绩汇总")
        print("0. 退出")
        print("=" * 60)

        choice = input("请选择操作 [0-10]: ").strip()

        if choice == '1':
            # 查看账户概览
            account = pm.get_account_info()
            print("\n💰 账户概览")
            print("-" * 40)
            print(f"总资产: ¥{account['total_value']:,.2f}")
            print(f"现金: ¥{account['cash']:,.2f}")
            print(f"持仓市值: ¥{account['positions_value']:,.2f}")
            pnl_sign = '+' if account['total_pnl'] >= 0 else ''
            print(f"总盈亏: ¥{pnl_sign}{account['total_pnl']:,.2f} ({pnl_sign}{account['total_pnl_pct']:.2f}%)")

        elif choice == '2':
            # 查看当前持仓
            positions = pm.get_all_positions()
            if positions.empty:
                print("\n📭 暂无持仓")
            else:
                print("\n📈 当前持仓")
                print("-" * 80)
                for _, pos in positions.iterrows():
                    pnl_sign = '+' if pos['profit_loss'] >= 0 else ''
                    print(f"{pos['code']} | {pos['shares']:,}股 | 成本¥{pos['cost_price']:.2f} | 现价¥{pos['current_price']:.2f} | 盈亏{pnl_sign}{pos['profit_pct']:.2f}%")

        elif choice == '3':
            # 买入股票
            print("\n🟢 买入股票")
            code = input("股票代码: ").strip().upper()
            try:
                shares = int(input("股数: "))
                price = float(input("买入价格: "))
                name = input("股票名称（可选）: ").strip() or None
                strategy = input("策略名称（可选）: ").strip() or None
                notes = input("备注（可选）: ").strip() or None

                pm.add_position(code, shares, price, name, strategy, notes)
            except ValueError:
                print("❌ 输入格式错误")

        elif choice == '4':
            # 卖出股票
            print("\n🔴 卖出股票")
            code = input("股票代码: ").strip().upper()
            try:
                shares = int(input("股数: "))
                price = float(input("卖出价格: "))
                reason = input("卖出原因（可选）: ").strip() or None

                pm.sell_position(code, shares, price, reason)
            except ValueError:
                print("❌ 输入格式错误")

        elif choice == '5':
            # 更新价格
            print("\n🔄 更新股票价格")
            positions = pm.get_all_positions()
            if positions.empty:
                print("暂无持仓需要更新")
            else:
                prices = {}
                for code in positions['code'].unique():
                    try:
                        price_input = input(f"{code} 当前价格: ").strip()
                        if price_input:
                            prices[code] = float(price_input)
                    except ValueError:
                        print(f"跳过 {code}")

                if prices:
                    pm.update_prices(prices)

        elif choice == '6':
            # 交易历史
            trades = pm.get_trade_history(limit=20)
            if trades.empty:
                print("\n📭 暂无交易记录")
            else:
                print("\n📝 最近交易记录")
                print("-" * 80)
                for _, trade in trades.iterrows():
                    action = '买入' if trade['action'] == 'buy' else '卖出'
                    print(f"{trade['date']} | {action} {trade['code']} | {trade['shares']:,}股@¥{trade['price']:.2f} | ¥{trade['amount']:,.2f}")

        elif choice == '7':
            # 风险提醒
            alerts = pm.get_alerts()
            if alerts.empty:
                print("\n✅ 暂无未读提醒")
            else:
                print("\n⚠️ 风险提醒")
                print("-" * 60)
                for _, alert in alerts.iterrows():
                    print(f"{alert['date']} | {alert['message']}")

                if input("\n标记为已读？(y/n): ").lower() == 'y':
                    pm.mark_alerts_read()

        elif choice == '8':
            # 生成报告
            pm.generate_html_report()

        elif choice == '9':
            # 设置初始资金
            try:
                amount = float(input("初始资金金额: "))
                if input(f"确认设置初始资金为 ¥{amount:,.2f}？(y/n): ").lower() == 'y':
                    pm.set_initial_capital(amount)
            except ValueError:
                print("❌ 输入格式错误")

        elif choice == '10':
            # 业绩汇总
            summary = pm.get_performance_summary()
            print("\n📊 业绩汇总")
            print("-" * 40)
            print(f"持仓数量: {summary['positions_count']}")
            print(f"总交易次数: {summary['total_trades']}")
            print(f"  买入: {summary['buy_trades']}次")
            print(f"  卖出: {summary['sell_trades']}次")
            print(f"总交易费用: ¥{summary['total_fees']:,.2f}")
            print(f"现金比例: {summary['cash_ratio']:.1f}%")

            if summary['position_weights']:
                print("\n持仓占比:")
                for code, weight in sorted(summary['position_weights'].items(), key=lambda x: x[1], reverse=True):
                    print(f"  {code}: {weight:.1f}%")

        elif choice == '0':
            print("\n👋 再见！")
            pm.close()
            break

        else:
            print("❌ 无效选择，请重试")


if __name__ == '__main__':
    interactive_menu()
