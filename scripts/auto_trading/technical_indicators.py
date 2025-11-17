#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级技术指标库

提供专业级技术分析指标：
- Bollinger Bands（布林带）
- Ichimoku Cloud（一目均衡表）
- OBV（能量潮）
- VWAP（成交量加权平均价格）
- 市场情绪指标
- ATR（平均真实波幅）
- ADX（平均趋向指数）
- Stochastic（随机指标）

使用方法:
    from technical_indicators import TechnicalIndicators

    ti = TechnicalIndicators()
    data = ti.add_all_indicators(df)
    signals = ti.generate_composite_signal(df)
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime


class TechnicalIndicators:
    """
    技术指标计算器

    提供各种专业技术分析指标
    """

    def __init__(self):
        """初始化"""
        pass

    # ==================== 布林带 ====================

    def bollinger_bands(self, data: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """
        计算布林带

        参数:
            data: 包含close列的DataFrame
            period: 移动平均周期
            num_std: 标准差倍数

        返回:
            添加布林带列的DataFrame
        """
        df = data.copy()

        # 中轨（移动平均）
        df['bb_middle'] = df['close'].rolling(window=period).mean()

        # 标准差
        rolling_std = df['close'].rolling(window=period).std()

        # 上轨和下轨
        df['bb_upper'] = df['bb_middle'] + (rolling_std * num_std)
        df['bb_lower'] = df['bb_middle'] - (rolling_std * num_std)

        # 带宽（波动性指标）
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # %B（价格在带中的位置）
        df['bb_percent'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # 信号
        df['bb_signal'] = 0
        df.loc[df['close'] < df['bb_lower'], 'bb_signal'] = 1  # 超卖，买入信号
        df.loc[df['close'] > df['bb_upper'], 'bb_signal'] = -1  # 超买，卖出信号

        return df

    def bollinger_squeeze(self, data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """
        布林带收缩（低波动性，预示突破）

        返回:
            包含squeeze指标的DataFrame
        """
        df = self.bollinger_bands(data, period)

        # 带宽的历史百分位
        df['bb_width_percentile'] = df['bb_width'].rolling(window=50).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1]
        )

        # 收缩信号（带宽在低位）
        df['bb_squeeze'] = df['bb_width_percentile'] < 0.2

        return df

    # ==================== 一目均衡表 ====================

    def ichimoku_cloud(self, data: pd.DataFrame,
                       tenkan_period: int = 9,
                       kijun_period: int = 26,
                       senkou_b_period: int = 52,
                       displacement: int = 26) -> pd.DataFrame:
        """
        计算一目均衡表（Ichimoku Cloud）

        参数:
            data: 包含high, low, close列的DataFrame
            tenkan_period: 转换线周期（默认9）
            kijun_period: 基准线周期（默认26）
            senkou_b_period: 先行带B周期（默认52）
            displacement: 位移（默认26）

        返回:
            添加一目均衡表指标的DataFrame
        """
        df = data.copy()

        # 转换线（Tenkan-sen）- 短期均衡
        tenkan_high = df['high'].rolling(window=tenkan_period).max()
        tenkan_low = df['low'].rolling(window=tenkan_period).min()
        df['ichimoku_tenkan'] = (tenkan_high + tenkan_low) / 2

        # 基准线（Kijun-sen）- 中期均衡
        kijun_high = df['high'].rolling(window=kijun_period).max()
        kijun_low = df['low'].rolling(window=kijun_period).min()
        df['ichimoku_kijun'] = (kijun_high + kijun_low) / 2

        # 先行带A（Senkou Span A）- 云层上边界
        df['ichimoku_senkou_a'] = ((df['ichimoku_tenkan'] + df['ichimoku_kijun']) / 2).shift(displacement)

        # 先行带B（Senkou Span B）- 云层下边界
        senkou_b_high = df['high'].rolling(window=senkou_b_period).max()
        senkou_b_low = df['low'].rolling(window=senkou_b_period).min()
        df['ichimoku_senkou_b'] = ((senkou_b_high + senkou_b_low) / 2).shift(displacement)

        # 迟行线（Chikou Span）- 延迟确认
        df['ichimoku_chikou'] = df['close'].shift(-displacement)

        # 云层颜色（上升云/下降云）
        df['ichimoku_cloud_green'] = df['ichimoku_senkou_a'] > df['ichimoku_senkou_b']

        # 价格相对于云的位置
        cloud_top = df[['ichimoku_senkou_a', 'ichimoku_senkou_b']].max(axis=1)
        cloud_bottom = df[['ichimoku_senkou_a', 'ichimoku_senkou_b']].min(axis=1)

        df['ichimoku_above_cloud'] = df['close'] > cloud_top
        df['ichimoku_below_cloud'] = df['close'] < cloud_bottom
        df['ichimoku_in_cloud'] = ~df['ichimoku_above_cloud'] & ~df['ichimoku_below_cloud']

        # 综合信号
        df['ichimoku_signal'] = 0
        # 强烈买入：价格在云上方，转换线>基准线，云为绿色
        df.loc[
            df['ichimoku_above_cloud'] &
            (df['ichimoku_tenkan'] > df['ichimoku_kijun']) &
            df['ichimoku_cloud_green'],
            'ichimoku_signal'
        ] = 1

        # 强烈卖出：价格在云下方，转换线<基准线，云为红色
        df.loc[
            df['ichimoku_below_cloud'] &
            (df['ichimoku_tenkan'] < df['ichimoku_kijun']) &
            ~df['ichimoku_cloud_green'],
            'ichimoku_signal'
        ] = -1

        return df

    # ==================== OBV（能量潮） ====================

    def obv(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算OBV（On-Balance Volume）

        量价关系指标：
        - 价格上涨时累加成交量
        - 价格下跌时累减成交量

        返回:
            添加OBV指标的DataFrame
        """
        df = data.copy()

        # 计算OBV
        obv_values = [0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i - 1]:
                obv_values.append(obv_values[-1] + df['volume'].iloc[i])
            elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
                obv_values.append(obv_values[-1] - df['volume'].iloc[i])
            else:
                obv_values.append(obv_values[-1])

        df['obv'] = obv_values

        # OBV移动平均
        df['obv_ma'] = df['obv'].rolling(window=20).mean()

        # OBV趋势
        df['obv_trend'] = df['obv'] - df['obv_ma']

        # OBV背离检测
        # 价格新高但OBV未新高 = 顶背离（卖出信号）
        # 价格新低但OBV未新低 = 底背离（买入信号）
        df['obv_divergence'] = 0

        window = 20
        for i in range(window, len(df)):
            price_slice = df['close'].iloc[i - window:i + 1]
            obv_slice = df['obv'].iloc[i - window:i + 1]

            # 检查顶背离
            if df['close'].iloc[i] == price_slice.max() and df['obv'].iloc[i] < obv_slice.max():
                df.loc[df.index[i], 'obv_divergence'] = -1  # 顶背离

            # 检查底背离
            if df['close'].iloc[i] == price_slice.min() and df['obv'].iloc[i] > obv_slice.min():
                df.loc[df.index[i], 'obv_divergence'] = 1  # 底背离

        return df

    # ==================== VWAP ====================

    def vwap(self, data: pd.DataFrame, period: int = None) -> pd.DataFrame:
        """
        计算VWAP（Volume Weighted Average Price）

        成交量加权平均价格，机构常用基准价格

        参数:
            data: 包含high, low, close, volume的DataFrame
            period: 计算周期（None表示累积VWAP）

        返回:
            添加VWAP指标的DataFrame
        """
        df = data.copy()

        # 典型价格
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3

        # 累积VWAP
        df['vwap_cum'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()

        # 滚动VWAP
        if period:
            df['vwap_rolling'] = (
                    (df['typical_price'] * df['volume']).rolling(window=period).sum() /
                    df['volume'].rolling(window=period).sum()
            )
        else:
            df['vwap_rolling'] = df['vwap_cum']

        # VWAP偏离度
        df['vwap_deviation'] = (df['close'] - df['vwap_rolling']) / df['vwap_rolling'] * 100

        # VWAP信号
        df['vwap_signal'] = 0
        df.loc[df['close'] > df['vwap_rolling'], 'vwap_signal'] = 1  # 价格高于VWAP，看涨
        df.loc[df['close'] < df['vwap_rolling'], 'vwap_signal'] = -1  # 价格低于VWAP，看跌

        # VWAP标准差带
        if period:
            df['vwap_std'] = df['close'].rolling(window=period).std()
            df['vwap_upper'] = df['vwap_rolling'] + df['vwap_std']
            df['vwap_lower'] = df['vwap_rolling'] - df['vwap_std']

        return df

    # ==================== ATR（平均真实波幅） ====================

    def atr(self, data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算ATR（Average True Range）

        衡量市场波动性

        返回:
            添加ATR指标的DataFrame
        """
        df = data.copy()

        # 真实波幅
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        # ATR（指数移动平均）
        df['atr'] = df['true_range'].ewm(span=period, adjust=False).mean()

        # ATR百分比（相对于价格）
        df['atr_percent'] = df['atr'] / df['close'] * 100

        # 波动性等级
        atr_percentile = df['atr_percent'].rolling(window=100).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) >= 10 else 0.5
        )
        df['volatility_level'] = pd.cut(
            atr_percentile,
            bins=[0, 0.25, 0.5, 0.75, 1.0],
            labels=['低', '中低', '中高', '高']
        )

        # 清理临时列
        df.drop(['tr1', 'tr2', 'tr3'], axis=1, inplace=True)

        return df

    # ==================== ADX（平均趋向指数） ====================

    def adx(self, data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算ADX（Average Directional Index）

        衡量趋势强度（不关心方向）

        返回:
            添加ADX指标的DataFrame
        """
        df = data.copy()

        # +DM和-DM
        df['plus_dm'] = df['high'].diff()
        df['minus_dm'] = -df['low'].diff()

        df.loc[df['plus_dm'] < 0, 'plus_dm'] = 0
        df.loc[df['minus_dm'] < 0, 'minus_dm'] = 0
        df.loc[df['plus_dm'] < df['minus_dm'], 'plus_dm'] = 0
        df.loc[df['minus_dm'] < df['plus_dm'], 'minus_dm'] = 0

        # 真实波幅
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 平滑
        df['atr_adx'] = df['tr'].ewm(span=period, adjust=False).mean()
        df['plus_di'] = 100 * (df['plus_dm'].ewm(span=period, adjust=False).mean() / df['atr_adx'])
        df['minus_di'] = 100 * (df['minus_dm'].ewm(span=period, adjust=False).mean() / df['atr_adx'])

        # DX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])

        # ADX
        df['adx'] = df['dx'].ewm(span=period, adjust=False).mean()

        # 趋势强度
        df['trend_strength'] = pd.cut(
            df['adx'],
            bins=[0, 20, 25, 50, 75, 100],
            labels=['无趋势', '弱趋势', '强趋势', '非常强', '极端']
        )

        # 趋势方向信号
        df['adx_signal'] = 0
        df.loc[(df['adx'] > 25) & (df['plus_di'] > df['minus_di']), 'adx_signal'] = 1  # 上升趋势
        df.loc[(df['adx'] > 25) & (df['plus_di'] < df['minus_di']), 'adx_signal'] = -1  # 下降趋势

        # 清理
        df.drop(['plus_dm', 'minus_dm', 'tr', 'atr_adx', 'dx'], axis=1, inplace=True)

        return df

    # ==================== 随机指标（Stochastic） ====================

    def stochastic(self, data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """
        计算随机指标（Stochastic Oscillator）

        参数:
            data: 包含high, low, close的DataFrame
            k_period: %K周期
            d_period: %D周期（%K的移动平均）

        返回:
            添加随机指标的DataFrame
        """
        df = data.copy()

        # %K
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        df['stoch_k'] = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)

        # %D（%K的移动平均）
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()

        # 信号
        df['stoch_signal'] = 0
        # 超卖区域（<20）且金叉
        df.loc[
            (df['stoch_k'] < 20) & (df['stoch_k'] > df['stoch_d']),
            'stoch_signal'
        ] = 1

        # 超买区域（>80）且死叉
        df.loc[
            (df['stoch_k'] > 80) & (df['stoch_k'] < df['stoch_d']),
            'stoch_signal'
        ] = -1

        return df

    # ==================== 市场情绪指标 ====================

    def fear_greed_index(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算恐惧贪婪指数

        综合多个指标评估市场情绪

        返回:
            包含情绪指标的DataFrame
        """
        df = data.copy()

        # 1. 价格动量（RSI）
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))

        # 2. 波动性（相对于历史）
        df['volatility_score'] = df['close'].pct_change().rolling(20).std()
        vol_percentile = df['volatility_score'].rank(pct=True)

        # 3. 均线偏离度
        df['ma50'] = df['close'].rolling(50).mean()
        df['ma_deviation'] = (df['close'] - df['ma50']) / df['ma50'] * 100

        # 4. 新高新低比例（简化版）
        df['high_20d'] = df['high'].rolling(20).max()
        df['low_20d'] = df['low'].rolling(20).min()
        df['near_high'] = (df['close'] >= df['high_20d'] * 0.98).astype(int)
        df['near_low'] = (df['close'] <= df['low_20d'] * 1.02).astype(int)

        # 计算综合情绪指数 (0-100)
        # RSI贡献
        rsi_score = df['rsi'].fillna(50)

        # 波动性贡献（高波动=恐惧）
        vol_score = (1 - vol_percentile.fillna(0.5)) * 100

        # 均线偏离贡献
        ma_score = df['ma_deviation'].fillna(0).clip(-10, 10) * 5 + 50

        # 综合计算
        df['fear_greed_index'] = (rsi_score * 0.4 + vol_score * 0.3 + ma_score * 0.3)
        df['fear_greed_index'] = df['fear_greed_index'].clip(0, 100)

        # 情绪级别
        df['sentiment'] = pd.cut(
            df['fear_greed_index'],
            bins=[0, 20, 40, 60, 80, 100],
            labels=['极度恐惧', '恐惧', '中性', '贪婪', '极度贪婪']
        )

        # 清理临时列
        df.drop(['ma50', 'high_20d', 'low_20d', 'near_high', 'near_low', 'volatility_score'], axis=1, inplace=True)

        return df

    def put_call_ratio_proxy(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Put/Call比率代理指标

        使用价格和成交量推断市场情绪

        返回:
            包含P/C代理指标的DataFrame
        """
        df = data.copy()

        # 下跌成交量 vs 上涨成交量
        df['up_volume'] = df['volume'].where(df['close'] > df['close'].shift(1), 0)
        df['down_volume'] = df['volume'].where(df['close'] < df['close'].shift(1), 0)

        # 滚动比率
        df['volume_ratio'] = (
                df['down_volume'].rolling(10).sum() /
                (df['up_volume'].rolling(10).sum() + 1e-10)
        )

        # 情绪信号
        df['volume_sentiment'] = pd.cut(
            df['volume_ratio'],
            bins=[0, 0.7, 1.0, 1.3, float('inf')],
            labels=['极度乐观', '乐观', '悲观', '极度悲观']
        )

        # 清理
        df.drop(['up_volume', 'down_volume'], axis=1, inplace=True)

        return df

    # ==================== 综合功能 ====================

    def add_all_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        添加所有技术指标

        参数:
            data: 原始OHLCV数据

        返回:
            包含所有指标的DataFrame
        """
        df = data.copy()

        # 添加各指标
        df = self.bollinger_bands(df)
        df = self.obv(df)
        df = self.vwap(df, period=20)
        df = self.atr(df)
        df = self.stochastic(df)
        df = self.fear_greed_index(df)

        # 一目均衡表需要high和low
        if 'high' in df.columns and 'low' in df.columns:
            df = self.ichimoku_cloud(df)
            df = self.adx(df)

        return df

    def generate_composite_signal(self, data: pd.DataFrame) -> Dict:
        """
        生成综合交易信号

        基于多个技术指标的综合评分

        返回:
            综合信号字典
        """
        df = self.add_all_indicators(data)

        if len(df) == 0:
            return {'signal': 'hold', 'score': 0, 'reasons': []}

        latest = df.iloc[-1]
        score = 0
        reasons = []

        # 布林带信号
        if 'bb_signal' in latest:
            if latest['bb_signal'] == 1:
                score += 15
                reasons.append('布林带超卖')
            elif latest['bb_signal'] == -1:
                score -= 15
                reasons.append('布林带超买')

        # 一目均衡表信号
        if 'ichimoku_signal' in latest:
            if latest['ichimoku_signal'] == 1:
                score += 20
                reasons.append('一目均衡表看涨')
            elif latest['ichimoku_signal'] == -1:
                score -= 20
                reasons.append('一目均衡表看跌')

        # OBV背离
        if 'obv_divergence' in latest:
            if latest['obv_divergence'] == 1:
                score += 15
                reasons.append('OBV底背离')
            elif latest['obv_divergence'] == -1:
                score -= 15
                reasons.append('OBV顶背离')

        # VWAP信号
        if 'vwap_signal' in latest:
            if latest['vwap_signal'] == 1:
                score += 10
                reasons.append('价格高于VWAP')
            elif latest['vwap_signal'] == -1:
                score -= 10
                reasons.append('价格低于VWAP')

        # 随机指标
        if 'stoch_signal' in latest:
            if latest['stoch_signal'] == 1:
                score += 15
                reasons.append('随机指标超卖金叉')
            elif latest['stoch_signal'] == -1:
                score -= 15
                reasons.append('随机指标超买死叉')

        # ADX趋势
        if 'adx_signal' in latest:
            if latest['adx_signal'] == 1:
                score += 10
                reasons.append('ADX上升趋势')
            elif latest['adx_signal'] == -1:
                score -= 10
                reasons.append('ADX下降趋势')

        # 市场情绪
        if 'fear_greed_index' in latest:
            fgi = latest['fear_greed_index']
            if fgi < 25:
                score += 20
                reasons.append(f'极度恐惧({fgi:.1f})，逆势买入')
            elif fgi > 75:
                score -= 20
                reasons.append(f'极度贪婪({fgi:.1f})，考虑卖出')

        # 确定信号
        if score >= 30:
            signal = 'strong_buy'
        elif score >= 15:
            signal = 'buy'
        elif score <= -30:
            signal = 'strong_sell'
        elif score <= -15:
            signal = 'sell'
        else:
            signal = 'hold'

        return {
            'signal': signal,
            'score': score,
            'reasons': reasons,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def print_indicator_summary(self, data: pd.DataFrame):
        """打印指标摘要"""
        df = self.add_all_indicators(data)

        if len(df) == 0:
            print("无数据")
            return

        latest = df.iloc[-1]

        print("\n" + "=" * 60)
        print("📊 技术指标摘要")
        print("=" * 60)

        # 布林带
        if 'bb_middle' in latest:
            print(f"\n📈 布林带:")
            print(f"   上轨: {latest['bb_upper']:.2f}")
            print(f"   中轨: {latest['bb_middle']:.2f}")
            print(f"   下轨: {latest['bb_lower']:.2f}")
            print(f"   %B: {latest['bb_percent']:.2%}")
            print(f"   带宽: {latest['bb_width']:.4f}")

        # 一目均衡表
        if 'ichimoku_tenkan' in latest:
            print(f"\n☁️ 一目均衡表:")
            print(f"   转换线: {latest['ichimoku_tenkan']:.2f}")
            print(f"   基准线: {latest['ichimoku_kijun']:.2f}")
            cloud_pos = "云上方" if latest.get('ichimoku_above_cloud', False) else \
                "云下方" if latest.get('ichimoku_below_cloud', False) else "云中"
            print(f"   位置: {cloud_pos}")

        # OBV
        if 'obv' in latest:
            print(f"\n📊 OBV (能量潮):")
            print(f"   OBV: {latest['obv']:,.0f}")
            print(f"   趋势: {'上升' if latest['obv_trend'] > 0 else '下降'}")

        # VWAP
        if 'vwap_rolling' in latest:
            print(f"\n💹 VWAP:")
            print(f"   VWAP: {latest['vwap_rolling']:.2f}")
            print(f"   偏离度: {latest['vwap_deviation']:.2f}%")

        # ATR
        if 'atr' in latest:
            print(f"\n📉 ATR (波动性):")
            print(f"   ATR: {latest['atr']:.4f}")
            print(f"   ATR%: {latest['atr_percent']:.2f}%")
            print(f"   波动等级: {latest.get('volatility_level', 'N/A')}")

        # 随机指标
        if 'stoch_k' in latest:
            print(f"\n🎲 随机指标:")
            print(f"   %K: {latest['stoch_k']:.2f}")
            print(f"   %D: {latest['stoch_d']:.2f}")

        # 情绪指标
        if 'fear_greed_index' in latest:
            print(f"\n😱 恐惧贪婪指数:")
            print(f"   指数: {latest['fear_greed_index']:.1f}")
            print(f"   情绪: {latest.get('sentiment', 'N/A')}")

        # 综合信号
        composite = self.generate_composite_signal(data)
        print(f"\n🎯 综合信号:")
        print(f"   信号: {composite['signal']}")
        print(f"   评分: {composite['score']}")
        if composite['reasons']:
            print(f"   原因:")
            for reason in composite['reasons']:
                print(f"      • {reason}")

        print("\n" + "=" * 60)


def demo():
    """演示技术指标"""
    print("\n" + "=" * 60)
    print("📊 高级技术指标库演示")
    print("=" * 60)

    # 生成模拟数据
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

    # 模拟OHLCV数据
    initial_price = 50
    prices = [initial_price]
    for _ in range(99):
        prices.append(prices[-1] * (1 + np.random.normal(0.001, 0.02)))

    data = pd.DataFrame({
        'date': dates,
        'open': [p * (1 + np.random.normal(0, 0.005)) for p in prices],
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': prices,
        'volume': [int(np.random.uniform(1e6, 1e7)) for _ in prices]
    })

    # 确保OHLC逻辑正确
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)

    # 创建指标计算器
    ti = TechnicalIndicators()

    # 打印指标摘要
    ti.print_indicator_summary(data)

    print("\n" + "=" * 60)
    print("✅ 技术指标演示完成")
    print("=" * 60)


if __name__ == '__main__':
    demo()
