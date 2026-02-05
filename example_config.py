"""
示例配置文件 - 展示不同的策略配置方案
"""

# ==================== 方案1：保守型配置 ====================
CONSERVATIVE_CONFIG = {
    # 更严格的筛选条件
    'PE_TTM_MAX': 15.0,  # 更低的PE要求
    'DIVIDEND_YIELD_MIN': 4.0,  # 更高的股息率要求
    'ATR_MIN_PERCENT': 2.0,  # 更高的波动率要求
    
    # 更谨慎的入场
    'ENTRY_SIGNAL_THRESHOLD': 0.85,  # MA120 * 85% 更深的回调才入场
    'FIRST_POSITION_RATIO': 0.05,  # 首次只用5%资金
    
    # 更密集的梯级
    'LADDER_DOWN': [
        (0.85, 0.05),  # 第一层
        (0.80, 0.10),  # 第二层
        (0.75, 0.15),  # 第三层
        (0.70, 0.20),  # 第四层
        (0.65, 0.25),  # 第五层
        (0.60, 0.25),  # 第六层
    ],
    
    # 更早止盈
    'SINGLE_LAYER_PROFIT': 0.08,  # 8%就止盈
    'FULL_CLEAR_THRESHOLD': 1.08,  # MA120 * 108% 全清
}

# ==================== 方案2：激进型配置 ====================
AGGRESSIVE_CONFIG = {
    # 相对宽松的筛选
    'PE_TTM_MAX': 25.0,
    'DIVIDEND_YIELD_MIN': 2.5,
    'ATR_MIN_PERCENT': 1.0,
    
    # 更早入场
    'ENTRY_SIGNAL_THRESHOLD': 0.90,  # MA120 * 90%
    'FIRST_POSITION_RATIO': 0.15,  # 首次用15%资金
    
    # 更大间距的梯级
    'LADDER_DOWN': [
        (0.90, 0.15),  # 第一层
        (0.80, 0.25),  # 第二层
        (0.70, 0.30),  # 第三层
        (0.60, 0.30),  # 第四层
    ],
    
    # 更高的止盈目标
    'SINGLE_LAYER_PROFIT': 0.15,  # 15%止盈
    'FULL_CLEAR_THRESHOLD': 1.15,  # MA120 * 115% 全清
}

# ==================== 方案3：ATR动态配置 ====================
DYNAMIC_ATR_CONFIG = {
    # 基础筛选
    'PE_TTM_MAX': 20.0,
    'DIVIDEND_YIELD_MIN': 3.0,
    'ATR_MIN_PERCENT': 1.5,
    
    # 启用ATR动态调整
    'USE_DYNAMIC_ATR': True,
    'ATR_MULTIPLIER': 3,  # 3倍ATR作为梯级间距
    
    # 基础梯级（会根据ATR动态调整）
    'ENTRY_SIGNAL_THRESHOLD': 0.88,
    'FIRST_POSITION_RATIO': 0.1,
    
    'LADDER_DOWN': [
        (0.88, 0.1),
        (0.80, 0.2),
        (0.70, 0.3),
        (0.60, 0.4),
    ],
    
    'SINGLE_LAYER_PROFIT': 0.12,
    'FULL_CLEAR_THRESHOLD': 1.12,
}

# ==================== 方案4：均衡型配置（默认推荐）====================
BALANCED_CONFIG = {
    'PE_TTM_MAX': 20.0,
    'DIVIDEND_YIELD_MIN': 3.0,
    'ATR_MIN_PERCENT': 1.5,
    
    'ENTRY_SIGNAL_THRESHOLD': 0.88,
    'FIRST_POSITION_RATIO': 0.1,
    
    'LADDER_DOWN': [
        (0.88, 0.1),
        (0.80, 0.2),
        (0.70, 0.3),
        (0.60, 0.4),
    ],
    
    'SINGLE_LAYER_PROFIT': 0.12,
    'FULL_CLEAR_THRESHOLD': 1.12,
    
    'USE_DYNAMIC_ATR': False,
}


def get_config(config_name='balanced'):
    """
    获取指定的配置方案
    
    Parameters:
    -----------
    config_name : str
        配置方案名称: 'conservative', 'aggressive', 'dynamic', 'balanced'
        
    Returns:
    --------
    dict : 配置字典
    """
    configs = {
        'conservative': CONSERVATIVE_CONFIG,
        'aggressive': AGGRESSIVE_CONFIG,
        'dynamic': DYNAMIC_ATR_CONFIG,
        'balanced': BALANCED_CONFIG,
    }
    
    return configs.get(config_name, BALANCED_CONFIG)


# 使用示例：
# from example_config import get_config
# from backtest_engine import BacktestEngine
# 
# config = get_config('conservative')  # 使用保守型配置
# engine = BacktestEngine(
#     start_date='2020-01-01',
#     end_date='2024-12-31',
#     initial_capital=1000000,
#     max_positions=5,
#     config=config  # 传入自定义配置
# )
