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
    df['atr'] = calculate_atr(df)
    df['atr_percent'] = calculate_atr_percent(df)
    
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
