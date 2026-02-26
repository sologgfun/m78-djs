"""
白马梯级轮动策略核心逻辑
"""
import pandas as pd
import numpy as np
from config import *
from indicators import add_all_indicators
from data_fetcher import is_etf_code


class LadderStrategy:
    """白马梯级轮动策略"""
    
    def __init__(self, config=None):
        """
        初始化策略
        
        Parameters:
        -----------
        config : dict
            策略配置参数（可选，使用默认配置）
        """
        self.config = config or {}
        
        # 第一阶段：筛选参数
        self.pe_max = self.config.get('PE_TTM_MAX', PE_TTM_MAX)
        self.dividend_min = self.config.get('DIVIDEND_YIELD_MIN', DIVIDEND_YIELD_MIN)
        self.atr_min = self.config.get('ATR_MIN_PERCENT', ATR_MIN_PERCENT)
        
        # 第二阶段：入场参数
        self.entry_threshold = self.config.get('ENTRY_SIGNAL_THRESHOLD', ENTRY_SIGNAL_THRESHOLD)
        self.first_position_ratio = self.config.get('FIRST_POSITION_RATIO', FIRST_POSITION_RATIO)
        
        # 第三阶段：梯级参数
        self.ladder_down = self.config.get('LADDER_DOWN', LADDER_DOWN)
        self.single_profit = self.config.get('SINGLE_LAYER_PROFIT', SINGLE_LAYER_PROFIT)
        self.enable_ma120_full_clear = self.config.get('ENABLE_MA120_FULL_CLEAR', ENABLE_MA120_FULL_CLEAR)
        self.full_clear = self.config.get('FULL_CLEAR_THRESHOLD', FULL_CLEAR_THRESHOLD)
        
        # ATR动态调整
        self.use_dynamic_atr = self.config.get('USE_DYNAMIC_ATR', USE_DYNAMIC_ATR)
        self.atr_multiplier = self.config.get('ATR_MULTIPLIER', ATR_MULTIPLIER)
        
        # 动态止盈（布林带上轨 + RSI超买/MACD顶背离）
        self.dynamic_take_profit = self.config.get('DYNAMIC_TAKE_PROFIT', DYNAMIC_TAKE_PROFIT)
        self.rsi_overbought = self.config.get('RSI_OVERBOUGHT', RSI_OVERBOUGHT)
    
    def screen_stocks(self, fundamentals_df, price_data_dict):
        """
        第一阶段：股票池筛选
        
        Parameters:
        -----------
        fundamentals_df : DataFrame
            基本面数据
        price_data_dict : dict
            {stock_code: DataFrame} 价格数据字典
            
        Returns:
        --------
        list : 符合条件的股票代码列表
        """
        qualified = []
        
        for _, row in fundamentals_df.iterrows():
            stock_code = row['stock_code']
            
            # ETF/LOF: 跳过 PE、股息率、市值等基本面筛选（这些指标不适用于 ETF）
            if is_etf_code(stock_code):
                # ETF 只检查价格数据和 ATR
                if stock_code not in price_data_dict:
                    continue
                df = price_data_dict[stock_code]
                if df is None or len(df) < 120:
                    continue
                df_with_indicators = add_all_indicators(df)
                latest_atr_percent = df_with_indicators['atr_percent'].iloc[-1]
                if latest_atr_percent < self.atr_min:
                    continue
                qualified.append(stock_code)
                continue
            
            # A 股: 完整的基本面筛选
            # 检查PE
            pe = row.get('pe_ttm', None)
            if pe is None or pe <= 0 or pe > self.pe_max:
                continue
            
            # 检查股息率
            dividend = row.get('dividend_yield', 0)
            if dividend < self.dividend_min:
                continue
            
            # 检查市值
            market_cap = row.get('market_cap', 0)
            if market_cap <= 0:
                continue
            
            # 检查价格数据是否可用
            if stock_code not in price_data_dict:
                continue
            
            df = price_data_dict[stock_code]
            if df is None or len(df) < 120:  # 至少需要120天数据
                continue
            
            # 计算ATR%
            df_with_indicators = add_all_indicators(df)
            latest_atr_percent = df_with_indicators['atr_percent'].iloc[-1]
            
            # 过滤"死鱼股"
            if latest_atr_percent < self.atr_min:
                continue
            
            qualified.append(stock_code)
        
        return qualified
    
    def check_entry_signal(self, df, portfolio_manager=None, stock_code=None):
        """
        第二阶段：检查是否触发入场信号
        
        Parameters:
        -----------
        df : DataFrame
            带有指标的价格数据
        portfolio_manager : StockPositionManager
            该股票的持仓管理器（可选）
        stock_code : str
            股票代码
            
        Returns:
        --------
        tuple : (是否触发, 入场价格, MA120参考价, 层级索引)
        """
        if len(df) < 120:
            return False, None, None, None
        
        current_price = df['close'].iloc[-1]
        ma120 = df['ma120'].iloc[-1]
        
        if pd.isna(ma120):
            return False, None, None, None
        
        # 如果还没有持仓，检查是否触发首次入场
        if portfolio_manager is None or portfolio_manager.is_empty():
            threshold_price = ma120 * self.entry_threshold
            if current_price <= threshold_price:
                return True, current_price, ma120, 0  # 层级0
        
        return False, None, None, None
    
    def check_add_position_signal(self, df, portfolio_manager):
        """
        第三阶段：检查是否需要加仓（向下补仓）
        
        Parameters:
        -----------
        df : DataFrame
            带有指标的价格数据
        portfolio_manager : StockPositionManager
            该股票的持仓管理器
            
        Returns:
        --------
        list : [(层级索引, 目标价格, 资金比例), ...]
        """
        if portfolio_manager.is_empty() or portfolio_manager.entry_ma120 is None:
            return []
        
        current_price = df['close'].iloc[-1]
        ma120_ref = portfolio_manager.entry_ma120
        
        signals = []
        
        # 检查每个梯级
        for i, (ratio, fund_ratio) in enumerate(self.ladder_down):
            # 跳过第一层（已经在入场时买入）
            if i == 0:
                continue
            
            # 检查该层是否已经持有
            if portfolio_manager.has_layer(i):
                continue
            
            # 检查价格是否触及该层
            target_price = ma120_ref * ratio
            if current_price <= target_price:
                signals.append((i, target_price, fund_ratio))
        
        return signals
    
    def check_take_profit_signal(self, df, portfolio_manager):
        """
        第三阶段：检查是否需要止盈
        
        止盈规则（按优先级）：
        1. 强制止盈：股价 >= 当日MA120 × full_clear_threshold（默认112%）
        2. 动态止盈（可选）：触及布林带上轨 且 (RSI超买 或 MACD顶背离)
        3. 单层止盈：单层收益率达标
        
        Returns:
        --------
        tuple : (是否全仓清空, [需要止盈的层级索引], 卖出原因字符串)
        """
        if portfolio_manager.is_empty():
            return False, [], ''
        
        current_price = df['close'].iloc[-1]
        
        # 规则1：MA120 强制止盈（使用当日实时 MA120）
        if self.enable_ma120_full_clear:
            ma120_today = df['ma120'].iloc[-1] if 'ma120' in df.columns else None
            if ma120_today is not None and not pd.isna(ma120_today):
                full_clear_price = ma120_today * self.full_clear
                if current_price >= full_clear_price:
                    pct = int(self.full_clear * 100)
                    return True, [], f'MA120强制止盈(>{pct}%)'
        
        # 规则2：动态止盈 — 布林带上轨 + (RSI超买 或 MACD顶背离)
        if self.dynamic_take_profit and len(df) >= 26:
            boll_upper = df['boll_upper'].iloc[-1] if 'boll_upper' in df.columns else None
            rsi_val = df['rsi'].iloc[-1] if 'rsi' in df.columns else None
            macd_hist = df['macd_hist'].iloc[-1] if 'macd_hist' in df.columns else None
            macd_hist_prev = df['macd_hist'].iloc[-2] if 'macd_hist' in df.columns and len(df) >= 2 else None
            
            at_boll_upper = (boll_upper is not None and not pd.isna(boll_upper) 
                            and current_price >= boll_upper)
            is_rsi_overbought = (rsi_val is not None and not pd.isna(rsi_val) 
                                and rsi_val >= self.rsi_overbought)
            is_macd_divergence = False
            if 'macd_dif' in df.columns:
                from indicators import detect_macd_top_divergence
                div_series = detect_macd_top_divergence(df, lookback=60)
                if len(div_series) > 0 and div_series.iloc[-1]:
                    is_macd_divergence = True
            is_macd_turning = (macd_hist is not None and macd_hist_prev is not None
                              and not pd.isna(macd_hist) and not pd.isna(macd_hist_prev)
                              and macd_hist_prev > 0 and macd_hist <= 0)
            
            if at_boll_upper and (is_rsi_overbought or is_macd_divergence or is_macd_turning):
                details = []
                if is_rsi_overbought:
                    details.append(f'RSI={rsi_val:.0f}')
                if is_macd_divergence:
                    details.append('MACD顶背离')
                if is_macd_turning:
                    details.append('MACD翻负')
                reason = f'动态止盈(BOLL上轨+{"+".join(details)})'
                return True, [], reason
        
        # 规则3：单层止盈
        layers_to_sell = []
        for layer in portfolio_manager.layers:
            profit_rate = layer.profit_rate(current_price)
            if profit_rate >= self.single_profit:
                layers_to_sell.append(layer.layer_index)
        
        if layers_to_sell:
            pct = int(self.single_profit * 100)
            return False, layers_to_sell, f'单层止盈({pct}%)'
        
        return False, [], ''
    
    def calculate_position_size(self, available_cash, fund_ratio, current_price):
        """
        计算建仓金额
        
        Parameters:
        -----------
        available_cash : float
            可用资金
        fund_ratio : float
            资金使用比例
        current_price : float
            当前价格
            
        Returns:
        --------
        float : 建仓金额
        """
        target_amount = available_cash * fund_ratio
        
        # 确保至少能买100股
        min_amount = current_price * 100 * 1.01  # 1.01是考虑手续费
        
        return max(target_amount, min_amount)
    
    def get_dynamic_ladders(self, atr_percent):
        """
        根据ATR%动态调整梯级
        
        Parameters:
        -----------
        atr_percent : float
            当前ATR%
            
        Returns:
        --------
        list : 动态梯级列表 [(ratio, fund_ratio), ...]
        """
        if not self.use_dynamic_atr:
            return self.ladder_down
        
        # 基于ATR%计算梯级间距
        step = atr_percent * self.atr_multiplier / 100
        
        # 生成新的梯级
        dynamic_ladders = []
        base_ratio = self.entry_threshold
        
        for i, (_, fund_ratio) in enumerate(self.ladder_down):
            ratio = base_ratio - (step * i)
            ratio = max(ratio, 0.4)  # 最低不低于40%
            dynamic_ladders.append((ratio, fund_ratio))
        
        return dynamic_ladders
