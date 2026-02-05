"""
持仓管理模块
"""
import pandas as pd
from datetime import datetime


class Position:
    """单个持仓层级"""
    
    def __init__(self, stock_code, stock_name, buy_date, buy_price, shares, layer_index):
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.shares = shares
        self.layer_index = layer_index  # 梯级层数（0,1,2,3）
        self.target_profit_rate = 0.12  # 目标止盈率
        
    def current_value(self, current_price):
        """当前市值"""
        return self.shares * current_price
    
    def profit_rate(self, current_price):
        """收益率"""
        return (current_price - self.buy_price) / self.buy_price
    
    def profit_amount(self, current_price):
        """盈亏金额"""
        return (current_price - self.buy_price) * self.shares
    
    def __repr__(self):
        return f"Position({self.stock_code}, Layer{self.layer_index}, {self.shares}股@{self.buy_price:.2f})"


class StockPositionManager:
    """单只股票的持仓管理器"""
    
    def __init__(self, stock_code, stock_name):
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.layers = []  # 存储各层持仓
        self.entry_ma120 = None  # 首次入场时的MA120价格
        
    def add_layer(self, buy_date, buy_price, shares, layer_index):
        """添加一层持仓"""
        position = Position(self.stock_code, self.stock_name, buy_date, 
                          buy_price, shares, layer_index)
        self.layers.append(position)
        
    def remove_layer(self, layer_index):
        """移除指定层级的持仓"""
        self.layers = [p for p in self.layers if p.layer_index != layer_index]
        
    def clear_all(self):
        """清空所有持仓"""
        self.layers = []
        self.entry_ma120 = None
        
    def total_shares(self):
        """总持股数"""
        return sum(p.shares for p in self.layers)
    
    def total_cost(self):
        """总成本"""
        return sum(p.buy_price * p.shares for p in self.layers)
    
    def avg_cost(self):
        """平均成本"""
        total = self.total_shares()
        if total == 0:
            return 0
        return self.total_cost() / total
    
    def total_value(self, current_price):
        """总市值"""
        return sum(p.current_value(current_price) for p in self.layers)
    
    def total_profit(self, current_price):
        """总盈亏"""
        return sum(p.profit_amount(current_price) for p in self.layers)
    
    def has_layer(self, layer_index):
        """检查是否已有某层持仓"""
        return any(p.layer_index == layer_index for p in self.layers)
    
    def get_layer(self, layer_index):
        """获取指定层级的持仓"""
        for p in self.layers:
            if p.layer_index == layer_index:
                return p
        return None
    
    def is_empty(self):
        """是否空仓"""
        return len(self.layers) == 0


class Portfolio:
    """投资组合管理器"""
    
    def __init__(self, initial_capital, commission_rate=0.0003, stamp_tax=0.001):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.stamp_tax = stamp_tax
        
        # 持仓管理
        self.positions = {}  # {stock_code: StockPositionManager}
        
        # 交易记录
        self.trades = []
        
        # 每日统计
        self.daily_stats = []
        
    def get_or_create_position_manager(self, stock_code, stock_name):
        """获取或创建股票持仓管理器"""
        if stock_code not in self.positions:
            self.positions[stock_code] = StockPositionManager(stock_code, stock_name)
        return self.positions[stock_code]
    
    def buy(self, date, stock_code, stock_name, price, amount, layer_index, ma120_ref=None, target_profit_rate=0.12, **extra):
        """
        买入操作
        
        Parameters:
        -----------
        date : str
            交易日期
        stock_code : str
            股票代码
        stock_name : str
            股票名称
        price : float
            买入价格
        amount : float
            买入金额
        layer_index : int
            梯级层数
        ma120_ref : float
            首次入场时的MA120参考价格
        target_profit_rate : float
            目标止盈率（默认12%）
        """
        # 计算手续费
        commission = amount * self.commission_rate
        total_cost = amount + commission
        
        # 检查资金是否足够
        if total_cost > self.cash:
            return False
        
        # 计算股数（A股以100股为单位）
        shares = int(amount / price / 100) * 100
        if shares == 0:
            return False
        
        actual_amount = shares * price
        actual_commission = actual_amount * self.commission_rate
        actual_total_cost = actual_amount + actual_commission
        
        # 扣除资金
        self.cash -= actual_total_cost
        
        # 添加持仓
        pm = self.get_or_create_position_manager(stock_code, stock_name)
        pm.add_layer(date, price, shares, layer_index)
        
        # 记录首次入场的MA120
        if ma120_ref is not None and pm.entry_ma120 is None:
            pm.entry_ma120 = ma120_ref
        
        # 计算目标价（买入价 * (1 + 目标止盈率)）
        target_price = price * (1 + target_profit_rate)
        
        # 记录交易
        trade = {
            'date': date,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'amount': actual_amount,
            'commission': actual_commission,
            'layer_index': layer_index,
            'target_price': target_price,  # 目标价
        }
        # 附加额外元数据（股息率、大盘点数、120线等）
        trade.update(extra)
        self.trades.append(trade)
        
        return True
    
    def sell(self, date, stock_code, price, layer_index=None, sell_all=False, **extra):
        """
        卖出操作
        
        Parameters:
        -----------
        date : str
            交易日期
        stock_code : str
            股票代码
        price : float
            卖出价格
        layer_index : int
            卖出的层级（None表示卖出所有）
        sell_all : bool
            是否全仓清空
        extra : dict
            附加元数据（股息率、大盘点数、120线等）
        """
        if stock_code not in self.positions:
            return False
        
        pm = self.positions[stock_code]
        
        if sell_all:
            # 卖出所有层级
            layers_to_sell = pm.layers.copy()
        elif layer_index is not None:
            # 卖出指定层级
            layer = pm.get_layer(layer_index)
            if layer is None:
                return False
            layers_to_sell = [layer]
        else:
            return False
        
        total_sold = 0
        for layer in layers_to_sell:
            shares = layer.shares
            amount = shares * price
            commission = amount * self.commission_rate
            stamp_tax = amount * self.stamp_tax
            total_cost = commission + stamp_tax
            net_amount = amount - total_cost
            
            # 增加资金
            self.cash += net_amount
            total_sold += shares
            
            # 计算持仓天数
            try:
                buy_dt = pd.to_datetime(layer.buy_date)
                sell_dt = pd.to_datetime(date)
                holding_days = (sell_dt - buy_dt).days
            except Exception:
                holding_days = 0

            # 记录交易
            trade = {
                'date': date,
                'stock_code': stock_code,
                'stock_name': pm.stock_name,
                'action': 'SELL_ALL' if sell_all else 'SELL_LAYER',
                'price': price,
                'shares': shares,
                'amount': amount,
                'commission': commission,
                'stamp_tax': stamp_tax,
                'layer_index': layer.layer_index,
                'buy_price': layer.buy_price,
                'buy_date': layer.buy_date,
                'profit_rate': layer.profit_rate(price),
                'profit_amount': layer.profit_amount(price),
                'holding_days': holding_days,
            }
            # 附加额外元数据（股息率、大盘点数、120线等）
            trade.update(extra)
            self.trades.append(trade)
            
            # 移除持仓
            pm.remove_layer(layer.layer_index)
        
        # 如果该股票已空仓，删除管理器
        if pm.is_empty():
            del self.positions[stock_code]
        
        return total_sold > 0
    
    def total_value(self, current_prices):
        """
        计算总资产
        
        Parameters:
        -----------
        current_prices : dict
            {stock_code: current_price}
        """
        stock_value = 0
        for stock_code, pm in self.positions.items():
            if stock_code in current_prices:
                stock_value += pm.total_value(current_prices[stock_code])
        
        return self.cash + stock_value
    
    def record_daily_stats(self, date, current_prices, index_price=None):
        """记录每日统计"""
        total_value = self.total_value(current_prices)
        
        # 记录每只股票的持仓层数 (用于操作状态图)
        stock_layers = {}
        for stock_code, pm in self.positions.items():
            stock_layers[stock_code] = len(pm.layers)

        stat = {
            'date': date,
            'cash': self.cash,
            'stock_value': total_value - self.cash,
            'total_value': total_value,
            'return': (total_value - self.initial_capital) / self.initial_capital,
            'positions_count': len(self.positions),
            'index_price': index_price,
            'stock_layers': stock_layers  # 新增：每只股票的持仓状态
        }
        self.daily_stats.append(stat)
    
    def get_trades_df(self):
        """获取交易记录DataFrame"""
        return pd.DataFrame(self.trades)
    
    def get_daily_stats_df(self):
        """获取每日统计DataFrame"""
        return pd.DataFrame(self.daily_stats)
