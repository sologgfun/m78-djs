"""
配置文件 - 白马梯级轮动策略
"""

# ==================== 策略参数 ====================

# 第一阶段：股票池筛选参数
PE_TTM_MAX = 20.0  # PE(TTM) 上限
DIVIDEND_YIELD_MIN = 3.0  # 股息率下限（%）
MARKET_CAP_PERCENTILE = 10  # 市值前N%

# 第二阶段：首次入场参数
ENTRY_SIGNAL_THRESHOLD = 0.88  # MA120 * 88% 触发首次入场
FIRST_POSITION_RATIO = 0.1  # 首次入场使用10%资金

# 第三阶段：梯级管理参数
# 向下加仓梯度（相对于MA120的比例，资金比例）
LADDER_DOWN = [
    (0.88, 0.1),  # MA120 * 88%，使用10%资金（第一层）
    (0.80, 0.2),  # MA120 * 80%，使用20%资金（第二层）
    (0.70, 0.3),  # MA120 * 70%，使用30%资金（第三层）
    (0.60, 0.4),  # MA120 * 60%，使用40%资金（第四层）
]

# 向上止盈参数
SINGLE_LAYER_PROFIT = 0.12  # 单层止盈比例 12%
ENABLE_MA120_FULL_CLEAR = True  # 是否启用 MA120 全仓清空
FULL_CLEAR_THRESHOLD = 1.12  # 当日MA120 * 112% 全仓清空

# ATR参数
ATR_PERIOD = 14  # ATR计算周期
ATR_MIN_PERCENT = 1.5  # 最小ATR%要求，过滤"死鱼股"
USE_DYNAMIC_ATR = False  # 是否使用ATR%动态调整梯度
ATR_MULTIPLIER = 3  # ATR倍数用于动态梯度

# 动态止盈参数（布林带+RSI/MACD）
DYNAMIC_TAKE_PROFIT = False  # 是否启用动态止盈
RSI_PERIOD = 14  # RSI 计算周期
RSI_OVERBOUGHT = 70  # RSI 超买阈值
BOLL_PERIOD = 20  # 布林带周期
BOLL_STD = 2  # 布林带标准差倍数
MACD_FAST = 12  # MACD 快线周期
MACD_SLOW = 26  # MACD 慢线周期
MACD_SIGNAL = 9  # MACD 信号线周期

# ==================== 回测参数 ====================

# 回测时间范围
START_DATE = "2015-01-01"
END_DATE = "2025-12-31"

# 资金管理
INITIAL_CAPITAL = 1000000  # 初始资金100万
MAX_POSITIONS = 5  # 最大同时持仓股票数
COMMISSION_RATE = 0.0003  # 手续费率 0.03%
STAMP_TAX = 0.001  # 印花税 0.1%（仅卖出）
MIN_TRADE_AMOUNT = 5000  # 最小交易金额

# 数据参数
DATA_CACHE_DIR = "./data_cache"  # 数据缓存目录
USE_CACHE = True  # 是否使用缓存数据

# 输出参数
OUTPUT_DIR = "./backtest_results"  # 结果输出目录
SAVE_TRADES = True  # 是否保存每笔交易明细
SAVE_DAILY_POSITIONS = True  # 是否保存每日持仓
