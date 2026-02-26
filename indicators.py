"""
技术指标计算模块
"""
import pandas as pd
import numpy as np


def calculate_ma(df, period):
    """计算移动平均线"""
    return df['close'].rolling(window=period).mean()


def calculate_atr(df, period=14):
    """
    计算ATR（Average True Range）
    
    Parameters:
    -----------
    df : DataFrame
        包含 high, low, close 列的数据框
    period : int
        ATR计算周期
        
    Returns:
    --------
    Series : ATR值
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # 计算真实波幅TR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 计算ATR（使用指数移动平均）
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_atr_percent(df, period=14):
    """
    计算ATR%（ATR占当前价格的百分比）
    
    Returns:
    --------
    Series : ATR%值
    """
    atr = calculate_atr(df, period)
    atr_percent = (atr / df['close']) * 100
    return atr_percent


def calculate_rsi(df, period=14):
    """计算RSI（相对强弱指标）"""
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(df, period=20, std_dev=2):
    """计算布林带（中轨、上轨、下轨）"""
    mid = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return mid, upper, lower


def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD（DIF、DEA、MACD柱）"""
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def detect_macd_top_divergence(df, lookback=60):
    """
    检测MACD顶背离：股价创新高但MACD DIF未创新高。
    返回布尔 Series，True 表示当日出现顶背离信号。
    """
    close = df['close']
    dif = df['macd_dif']
    result = pd.Series(False, index=df.index)

    for i in range(lookback, len(df)):
        window_close = close.iloc[i - lookback:i + 1]
        window_dif = dif.iloc[i - lookback:i + 1]

        if pd.isna(window_dif.iloc[-1]):
            continue

        current_close = window_close.iloc[-1]
        current_dif = window_dif.iloc[-1]
        prev_high_close = window_close.iloc[:-1].max()
        prev_high_idx = window_close.iloc[:-1].idxmax()

        if current_close >= prev_high_close:
            prev_dif_at_high = dif.loc[prev_high_idx] if prev_high_idx in dif.index else np.nan
            if pd.notna(prev_dif_at_high) and current_dif < prev_dif_at_high:
                result.iloc[i] = True

    return result


def add_all_indicators(df, ma_periods=[60, 120]):
    """
    为数据框添加所有技术指标
    
    Parameters:
    -----------
    df : DataFrame
        原始OHLC数据
    ma_periods : list
        需要计算的均线周期
        
    Returns:
    --------
    DataFrame : 添加了指标的数据框
    """
    df = df.copy()
    
    # 计算移动平均线
    for period in ma_periods:
        df[f'ma{period}'] = calculate_ma(df, period)
    
    # 计算ATR
    df['atr'] = calculate_atr(df, period=20)
    df['atr_percent'] = calculate_atr_percent(df, period=20)
    
    # RSI
    df['rsi'] = calculate_rsi(df)
    
    # 布林带
    df['boll_mid'], df['boll_upper'], df['boll_lower'] = calculate_bollinger_bands(df)
    
    # MACD
    df['macd_dif'], df['macd_dea'], df['macd_hist'] = calculate_macd(df)
    
    return df


def calculate_drawdown(equity_curve):
    """
    计算回撤序列
    
    Parameters:
    -----------
    equity_curve : Series
        权益曲线
        
    Returns:
    --------
    tuple : (回撤序列, 最大回撤)
    """
    # 计算累计最高点
    cum_max = equity_curve.expanding().max()
    
    # 计算回撤
    drawdown = (equity_curve - cum_max) / cum_max
    
    # 最大回撤
    max_drawdown = drawdown.min()
    
    return drawdown, max_drawdown


def calculate_sharpe_ratio(returns, risk_free_rate=0.02):
    """
    计算夏普比率
    
    Parameters:
    -----------
    returns : Series
        收益率序列
    risk_free_rate : float
        无风险利率（年化）
        
    Returns:
    --------
    float : 夏普比率
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0
    
    # 计算年化收益率
    annual_return = returns.mean() * 252
    
    # 计算年化波动率
    annual_std = returns.std() * np.sqrt(252)
    
    # 计算夏普比率
    sharpe = (annual_return - risk_free_rate) / annual_std
    
    return sharpe
