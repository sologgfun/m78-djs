"""
回测引擎
"""
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import *
from data_fetcher import DataFetcher
from strategy import LadderStrategy
from portfolio import Portfolio
from indicators import add_all_indicators, calculate_drawdown


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, start_date, end_date, initial_capital=1000000, 
                 max_positions=5, config=None):
        """
        初始化回测引擎
        
        Parameters:
        -----------
        start_date : str
            回测开始日期
        end_date : str
            回测结束日期
        initial_capital : float
            初始资金
        max_positions : int
            最大持仓股票数（用户选股模式下会被忽略）
        config : dict
            策略配置
        """
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.ignore_max_positions = False  # 是否忽略持仓限制（用户选股/条件选股时）
        
        # 初始化组件
        self.data_fetcher = DataFetcher(cache_dir=DATA_CACHE_DIR, use_cache=USE_CACHE)
        self.strategy = LadderStrategy(config)
        self.portfolio = Portfolio(initial_capital, COMMISSION_RATE, STAMP_TAX)
        
        # 数据存储
        self.stock_data = {}  # {stock_code: DataFrame}
        self.fundamentals = None
        self.name_map = {}  # {stock_code: stock_name}
        self.qualified_stocks = []
        self.index_data = {}  # {date_str: 上证指数收盘价}
        
        # 回测结果
        self.results = {}
        
        # 调试信息：记录买入机会
        self.missed_opportunities = {}  # {stock_code: [(date, reason), ...]}
    
    def load_data(self, stock_codes=None, is_auto_screen=False):
        """
        加载数据
        
        Parameters:
        -----------
        stock_codes : list
            指定股票代码列表（None则加载全市场）
        is_auto_screen : bool
            是否为条件选股模式
        """
        print("\n=== 第一阶段：加载数据 ===")
        
        # 获取股票列表
        # 条件选股等同于手动选股，不做策略过滤
        user_selected_codes = stock_codes is not None and len(stock_codes) > 0
        if stock_codes is None:
            stock_list = self.data_fetcher.get_stock_list()
            stock_codes = stock_list['code'].tolist()
        else:
            # 统一格式，避免后续匹配失败
            normalized = []
            for code in stock_codes:
                s = str(code)
                digits = "".join([c for c in s if c.isdigit()])
                if len(digits) >= 6:
                    normalized.append(digits[-6:])
                else:
                    normalized.append(s.zfill(6))
            # 去重但保留顺序
            seen = set()
            stock_codes = [c for c in normalized if not (c in seen or seen.add(c))]
        
        # 获取股票列表以构建名称映射
        # 用户指定了股票代码时，跳过全市场列表（太慢），名称从基本面数据中获取即可
        if user_selected_codes:
            print("构建股票名称映射表（从缓存快速查找）...")
            # 先尝试从本地缓存快速读取名称
            for code in stock_codes:
                name = self.data_fetcher._get_stock_name_from_cache(code)
                if name:
                    self.name_map[code] = name
        else:
            print("构建股票名称映射表...")
            full_stock_list = self.data_fetcher.get_stock_list()
            if full_stock_list is not None and not full_stock_list.empty:
                full_stock_list['code'] = full_stock_list['code'].astype(str).str.zfill(6)
                self.name_map = dict(zip(full_stock_list['code'], full_stock_list['name']))
        
        # 获取基本面数据
        print("获取基本面数据...")
        self.fundamentals = self.data_fetcher.batch_get_fundamentals(stock_codes)
        
        # 1. 从获取到的基本面数据中进一步填充名称映射表
        if self.fundamentals is not None and not self.fundamentals.empty:
            for _, row in self.fundamentals.iterrows():
                code = str(row['stock_code']).zfill(6)
                name = row.get('stock_name')
                # 确保名称有效（非空、非代码本身）
                if name and isinstance(name, str) and name.strip() and name != code:
                    self.name_map[code] = name.strip()
        
        # 2. 对于用户选定的股票，如果名称映射表中缺失或无效，发起单个请求强制获取名称
        if user_selected_codes:
            missing_names = [c for c in stock_codes if c not in self.name_map or not self.name_map[c]]
            if missing_names:
                print(f"正在手动补全 {len(missing_names)} 只股票的名称...")
                for code in tqdm(missing_names):
                    fund = self.data_fetcher.get_stock_fundamental(code)
                    if fund and fund.get('stock_name'):
                        name = fund['stock_name']
                        if isinstance(name, str) and name.strip() and name != code:
                            self.name_map[code] = name.strip()
                            print(f"  {code} → {name.strip()}")

        if self.fundamentals is None or len(self.fundamentals) == 0:
            print("警告：无法获取基本面数据")
            # 用户手动选股时：即使基本面失败，也继续流程，保证结果表至少包含所选股票
            if user_selected_codes:
                # 尽量从 name_map 获取名称
                names = [self.name_map.get(c, c) for c in stock_codes]
                self.fundamentals = pd.DataFrame({
                    'stock_code': stock_codes,
                    'stock_name': names,
                    'pe_ttm': [None] * len(stock_codes),
                    'market_cap': [None] * len(stock_codes),
                    'dividend_yield': [None] * len(stock_codes),
                })
            else:
                return
        
        print(f"获取到 {len(self.fundamentals)} 只股票的基本面数据")
        
        # 初步筛选符合基本条件的股票
        # - 若用户手动指定股票列表或条件选股：以指定列表为准，不做 PE/股息率过滤
        # - 若全市场回测：按策略参数做初筛，提高效率
        if user_selected_codes:
            filtered = self.fundamentals.copy()
            if is_auto_screen:
                print("\n条件选股模式，使用已筛选的股票池（不做策略过滤）")
            else:
                print("\n用户已指定股票池，跳过基本面初筛")
        else:
            print("\n初步筛选股票...")
            filtered = self.fundamentals[
                (self.fundamentals['pe_ttm'] > 0) &
                (self.fundamentals['pe_ttm'] < self.strategy.pe_max) &
                (self.fundamentals['dividend_yield'] >= self.strategy.dividend_min)
            ]
            print(f"初步筛选后剩余 {len(filtered)} 只股票")
        
        # 加载价格数据（多线程并发）
        print("\n加载股票价格数据...")
        valid_stocks = []
        
        if user_selected_codes:
            # 保持与用户选择一致的顺序
            codes_to_load = stock_codes
        else:
            # 限制数量以加快测试
            codes_to_load = filtered['stock_code'].tolist()[:100]

        num_stocks = len(codes_to_load)
        print(f"下载 {num_stocks} 只股票数据...")

        for stock_code in tqdm(codes_to_load, desc="下载进度"):
            try:
                df = self.data_fetcher.get_stock_daily_data(
                    stock_code, self.start_date, self.end_date
                )
                if df is not None and len(df) >= 120:
                    df = add_all_indicators(df)
                    self.stock_data[stock_code] = df
                    valid_stocks.append(stock_code)
                else:
                    data_len = len(df) if df is not None else 0
                    if data_len > 0:
                        print(f"  跳过 {stock_code}: 数据不足 ({data_len} < 120)")
            except Exception as e:
                print(f"  获取 {stock_code} 失败: {e}")
        
        print(f"成功加载 {len(valid_stocks)} 只股票的价格数据")
        
        # 显示每只股票的数据范围（仅显示前几只或用户关注的）
        if len(valid_stocks) <= 10:
            print("\n各股票数据范围:")
            for code in valid_stocks:
                df = self.stock_data.get(code)
                if df is not None and len(df) > 0:
                    min_date = df['date'].min()
                    max_date = df['date'].max()
                    name = self.name_map.get(code, code)
                    print(f"  {name}({code}): {len(df)}条 ({min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')})")
        
        # 最终筛选
        # - 用户手动选股/条件选股：以指定列表为准，不做任何过滤（逻辑完全一致）
        # - 全市场回测：按策略完整筛选（包括PE、股息、ATR%等）
        if user_selected_codes:
            # 用户选股/条件选股时，每只股票独立回测，忽略持仓限制
            self.ignore_max_positions = True
            self.qualified_stocks = stock_codes
            
            if is_auto_screen:
                print("\n条件选股模式：回测逻辑与手动选股完全一致")
                print(f"最终入池={len(stock_codes)}只（前端筛选结果，不做二次过滤）")
            else:
                print("\n用户手动选股：回测所有所选股票")
                print(f"最终入池={len(stock_codes)}只")
        else:
            print("\n最终筛选符合条件的股票（包括ATR%等技术指标）...")
            self.qualified_stocks = self.strategy.screen_stocks(
                self.fundamentals, self.stock_data
            )
        print(f"最终入池股票数量: {len(self.qualified_stocks)}")

        # 加载上证指数数据（用于记录大盘点数）
        print("\n加载上证指数数据...")
        self._load_index_data()
        print(f"上证指数数据天数: {len(self.index_data)}")

    def _load_index_data(self):
        """
        加载上证指数日线数据，用于在每笔交易中记录大盘点数。
        使用 akshare 获取上证指数 (sh000001)
        """
        try:
            import akshare as ak
            # stock_zh_index_daily: 新浪财经-指数-大盘指数
            # sh000001 = 上证指数
            df = ak.stock_zh_index_daily(symbol="sh000001")
            
            # 确保日期格式一致
            df['date'] = pd.to_datetime(df['date'])
            
            # 过滤日期范围
            start_dt = pd.to_datetime(self.start_date)
            end_dt = pd.to_datetime(self.end_date)
            
            mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
            df_slice = df.loc[mask]
            
            for _, row in df_slice.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                self.index_data[date_str] = float(row['close'])
                
        except Exception as e:
            print(f"  警告: 加载上证指数失败: {e}")

    def _get_trade_extra_fast(self, date_str, stock_code, row_idx, df):
        """快速版：获取交易附加元数据，直接用行索引避免 DataFrame 全表扫描"""
        extra = {}
        extra['index_price'] = self.index_data.get(date_str, 0)

        row = df.iloc[row_idx]

        ma120_val = round(float(row['ma120']), 2) if 'ma120' in df.columns and pd.notna(row['ma120']) else 0
        extra['ma120'] = ma120_val

        close_val = float(row['close'])
        if ma120_val > 0:
            extra['price_ma120_pct'] = round(close_val / ma120_val * 100, 2)
            extra['discount_ma120'] = round((close_val / ma120_val - 1) * 100, 2)
        else:
            extra['price_ma120_pct'] = 0
            extra['discount_ma120'] = 0

        extra['atr_pct'] = round(float(row['atr_percent']), 2) if 'atr_percent' in df.columns and pd.notna(row.get('atr_percent')) else 0

        if row_idx >= 20:
            avg_vol_20 = df['volume'].iloc[row_idx - 20:row_idx].mean()
            extra['volume_ratio'] = round(float(row['volume']) / avg_vol_20, 2) if avg_vol_20 > 0 else 0
        else:
            extra['volume_ratio'] = 0

        if self.fundamentals is not None and len(self.fundamentals) > 0:
            m = self.fundamentals[self.fundamentals['stock_code'] == stock_code]
            if len(m) > 0 and 'dividend_yield' in m.columns:
                val = m['dividend_yield'].iloc[0]
                extra['dividend_yield'] = round(float(val), 2) if pd.notna(val) else 0
            else:
                extra['dividend_yield'] = 0
        else:
            extra['dividend_yield'] = 0

        return extra

    def _get_trade_extra(self, date_str, stock_code):
        """
        获取每笔交易的附加元数据（交易专家视角）:

        核心指标:
        - index_price   : 上证指数收盘价（大盘环境）
        - ma120         : 该股票120日均线价格（策略参考线）
        - price_ma120_pct: 当前价格 / MA120 百分比（偏离度，核心决策依据）
        - atr_pct       : 当日 ATR%（波动率，衡量风险/机会）
        - volume_ratio  : 量比 = 当日成交量 / 20日均量（异动信号）
        - dividend_yield: 快照股息率（参考值）
        - cumulative_pnl: 该股票截至本笔交易的累计已实现盈亏
        """
        extra = {}

        # ---------- 大盘点数 ----------
        extra['index_price'] = self.index_data.get(date_str, 0)

        # ---------- 个股当日行情 ----------
        row = None
        if stock_code in self.stock_data:
            df = self.stock_data[stock_code]
            matched = df[df['date'] == date_str]
            if len(matched) > 0:
                row = matched.iloc[0]

        # MA120
        if row is not None and 'ma120' in row.index and pd.notna(row['ma120']):
            ma120_val = round(float(row['ma120']), 2)
        else:
            ma120_val = 0
        extra['ma120'] = ma120_val

        # 价格/MA120 偏离度 (%)
        if row is not None and ma120_val > 0:
            extra['price_ma120_pct'] = round(float(row['close']) / ma120_val * 100, 2)
            # 折价率：成交价低于120线多少 (负数=低于，正数=高于)
            extra['discount_ma120'] = round((float(row['close']) / ma120_val - 1) * 100, 2)
        else:
            extra['price_ma120_pct'] = 0
            extra['discount_ma120'] = 0

        # ATR%（当日波动率）
        if row is not None and 'atr_percent' in row.index and pd.notna(row['atr_percent']):
            extra['atr_pct'] = round(float(row['atr_percent']), 2)
        else:
            extra['atr_pct'] = 0

        # 量比 = 当日成交量 / 20日均量
        if row is not None and stock_code in self.stock_data:
            df = self.stock_data[stock_code]
            idx = matched.index[0]
            pos = df.index.get_loc(idx)
            if pos >= 20:
                avg_vol_20 = df['volume'].iloc[pos - 20:pos].mean()
                if avg_vol_20 > 0:
                    extra['volume_ratio'] = round(float(row['volume']) / avg_vol_20, 2)
                else:
                    extra['volume_ratio'] = 0
            else:
                extra['volume_ratio'] = 0
        else:
            extra['volume_ratio'] = 0

        # ---------- 股息率（快照参考值）----------
        if self.fundamentals is not None and len(self.fundamentals) > 0:
            m = self.fundamentals[self.fundamentals['stock_code'] == stock_code]
            if len(m) > 0 and 'dividend_yield' in m.columns:
                val = m['dividend_yield'].iloc[0]
                extra['dividend_yield'] = round(float(val), 2) if pd.notna(val) else 0
            else:
                extra['dividend_yield'] = 0
        else:
            extra['dividend_yield'] = 0

        # ---------- 累计已实现盈亏（本股票）----------
        cum_pnl = 0.0
        for t in self.portfolio.trades:
            if str(t.get('stock_code', '')) == stock_code and \
               t.get('action', '').startswith('SELL'):
                pa = t.get('profit_amount', 0)
                if pa and not (isinstance(pa, float) and np.isnan(pa)):
                    cum_pnl += float(pa)
        extra['cumulative_pnl'] = round(cum_pnl, 2)

        return extra

    def _lookup_stock_name(self, stock_code: str) -> str:
        """根据名称映射表或基本面表查询股票名称，失败则实时获取，最后回退为代码"""
        # 1. 优先从预加载的名称映射表中查找
        if stock_code in self.name_map:
            name = self.name_map[stock_code]
            if isinstance(name, str) and name.strip() and name != stock_code:
                return name.strip()
        
        # 2. 备选：从基本面数据中查找
        try:
            if self.fundamentals is not None and len(self.fundamentals) > 0:
                m = self.fundamentals[self.fundamentals['stock_code'] == stock_code]
                if len(m) > 0:
                    name = m['stock_name'].iloc[0]
                    if isinstance(name, str) and name.strip() and name != stock_code:
                        # 缓存到 name_map，避免重复查询
                        self.name_map[stock_code] = name.strip()
                        return name.strip()
        except Exception:
            pass
        
        # 3. 最后尝试：实时获取（仅在名称未找到时）
        try:
            fund = self.data_fetcher.get_stock_fundamental(stock_code)
            if fund and fund.get('stock_name'):
                name = fund['stock_name']
                if isinstance(name, str) and name.strip() and name != stock_code:
                    # 缓存结果
                    self.name_map[stock_code] = name.strip()
                    print(f"  实时获取股票名称: {stock_code} → {name.strip()}")
                    return name.strip()
        except Exception as e:
            print(f"  获取 {stock_code} 名称失败: {e}")
            
        return stock_code
    
    def run(self, progress_callback=None):
        """执行回测"""
        print("\n=== 第二阶段：执行回测 ===")
        
        # 显示策略参数
        print("\n策略参数:")
        print(f"  入场信号: MA120 × {self.strategy.entry_threshold:.0%}")
        print(f"  梯级配置: {self.strategy.ladder_down}")
        print(f"  单层止盈: {self.strategy.single_profit:.0%}")
        print(f"  全仓清空: MA120 × {self.strategy.full_clear:.0%}")
        print(f"  ATR%阈值: {self.strategy.atr_min}%")
        
        if len(self.qualified_stocks) == 0:
            print("没有符合条件的股票，回测结束")
            return None
        
        # 获取所有交易日
        all_dates = set()
        for df in self.stock_data.values():
            all_dates.update(df['date'].dt.strftime('%Y-%m-%d').tolist())
        
        trading_days = sorted(list(all_dates))
        total_days = len(trading_days)
        print(f"回测交易日数量: {total_days}")
        
        # 性能优化：预先构建日期索引缓存
        print("构建日期索引缓存...")
        self._date_index_cache = {}  # {stock_code: {date_str: end_idx}}
        for stock_code, df in self.stock_data.items():
            date_to_idx = {}
            df_dates = df['date'].dt.strftime('%Y-%m-%d').tolist()
            for i, d in enumerate(df_dates):
                date_to_idx[d] = i + 1  # +1 因为要包含当天
            self._date_index_cache[stock_code] = date_to_idx
        
        # 判断是否可以并发回测（用户选股/条件选股模式，每只股票独立）
        if self.ignore_max_positions and len(self.qualified_stocks) > 1:
            print(f"启用并发回测模式（{len(self.qualified_stocks)}只股票独立回测）...")
            self._run_parallel_backtest(trading_days, progress_callback)
        else:
            print("启用串行回测模式...")
            self._run_serial_backtest(trading_days, progress_callback)
        
        print("\n回测完成！")
        
        # 回测结束后，为未完成的买入计算当前盈亏
        self._calculate_uncompleted_trades_pnl(trading_days[-1] if trading_days else None)
    
    def _run_serial_backtest(self, trading_days, progress_callback):
        """串行回测（传统模式，股票之间有依赖关系）"""
        total_days = len(trading_days)
        for i, date_str in enumerate(tqdm(trading_days, desc="回测进度")):
            self._process_day(date_str)
            
            if progress_callback and (i % 5 == 0 or i == total_days - 1):
                percent = int(40 + (i / total_days) * 40)
                progress_callback(percent, f"正在回测: {date_str} ({i+1}/{total_days})")
    
    def _run_parallel_backtest(self, trading_days, progress_callback):
        """并发回测（用户选股模式，每只股票独立）— 性能优化版"""
        num_stocks = len(self.qualified_stocks)
        print(f"回测 {num_stocks} 只股票（逐只顺序执行，内部用 numpy 加速）...")
        print("注意：每只股票独立回测，不记录每日资产统计（因为资金独立）")

        strategy = self.strategy

        for si, stock_code in enumerate(tqdm(self.qualified_stocks, desc="回测进度")):
            stock_portfolio = Portfolio(100000, self.portfolio.commission_rate, self.portfolio.stamp_tax)
            stock_name = self._lookup_stock_name(stock_code)

            if stock_code not in self.stock_data:
                continue

            df = self.stock_data[stock_code]
            date_idx_map = self._date_index_cache.get(stock_code, {})

            close_arr = df['close'].values
            ma120_arr = df['ma120'].values if 'ma120' in df.columns else None

            for date_str in trading_days:
                end_idx = date_idx_map.get(date_str)
                if not end_idx or end_idx < 120:
                    continue

                idx = end_idx - 1
                current_price = float(close_arr[idx])
                current_ma120 = float(ma120_arr[idx]) if ma120_arr is not None else None

                if stock_code in stock_portfolio.positions:
                    pm = stock_portfolio.positions[stock_code]

                    # --- 快速止盈判断（内联，避免 DataFrame 切片） ---
                    is_full_clear = False
                    layers_to_sell = []
                    sell_reason = ''

                    # 规则1: MA120 强制止盈
                    if strategy.enable_ma120_full_clear and current_ma120 is not None and not np.isnan(current_ma120):
                        full_clear_price = current_ma120 * strategy.full_clear
                        if current_price >= full_clear_price:
                            is_full_clear = True
                            pct = int(strategy.full_clear * 100)
                            sell_reason = f'MA120强制止盈(>{pct}%)'

                    # 规则2: 动态止盈（需要完整 DataFrame，仅在开启时执行）
                    if not is_full_clear and strategy.dynamic_take_profit and end_idx >= 26:
                        df_until_today = df.iloc[:end_idx]
                        boll_upper = df_until_today['boll_upper'].iloc[-1] if 'boll_upper' in df.columns else None
                        rsi_val = df_until_today['rsi'].iloc[-1] if 'rsi' in df.columns else None
                        macd_hist_cur = df_until_today['macd_hist'].iloc[-1] if 'macd_hist' in df.columns else None
                        macd_hist_prev = df_until_today['macd_hist'].iloc[-2] if 'macd_hist' in df.columns and end_idx >= 2 else None

                        at_boll_upper = boll_upper is not None and not pd.isna(boll_upper) and current_price >= boll_upper
                        is_rsi_ob = rsi_val is not None and not pd.isna(rsi_val) and rsi_val >= strategy.rsi_overbought
                        is_macd_div = False
                        if 'macd_dif' in df.columns:
                            from indicators import detect_macd_top_divergence
                            div_s = detect_macd_top_divergence(df_until_today, lookback=60)
                            if len(div_s) > 0 and div_s.iloc[-1]:
                                is_macd_div = True
                        is_macd_turn = (macd_hist_cur is not None and macd_hist_prev is not None
                                        and not pd.isna(macd_hist_cur) and not pd.isna(macd_hist_prev)
                                        and macd_hist_prev > 0 and macd_hist_cur <= 0)

                        if at_boll_upper and (is_rsi_ob or is_macd_div or is_macd_turn):
                            is_full_clear = True
                            details = []
                            if is_rsi_ob: details.append(f'RSI={rsi_val:.0f}')
                            if is_macd_div: details.append('MACD顶背离')
                            if is_macd_turn: details.append('MACD翻负')
                            sell_reason = f'动态止盈(BOLL上轨+{"+".join(details)})'

                    # 规则3: 单层止盈
                    if not is_full_clear:
                        for layer in pm.layers:
                            if layer.profit_rate(current_price) >= strategy.single_profit:
                                layers_to_sell.append(layer.layer_index)
                        if layers_to_sell:
                            pct = int(strategy.single_profit * 100)
                            sell_reason = f'单层止盈({pct}%)'

                    if is_full_clear:
                        extra = self._get_trade_extra_fast(date_str, stock_code, idx, df)
                        extra['sell_reason'] = sell_reason
                        stock_portfolio.sell(date_str, stock_code, current_price, sell_all=True, **extra)
                    else:
                        for layer_idx in layers_to_sell:
                            extra = self._get_trade_extra_fast(date_str, stock_code, idx, df)
                            extra['sell_reason'] = sell_reason
                            stock_portfolio.sell(date_str, stock_code, current_price, layer_index=layer_idx, **extra)

                    # --- 快速加仓判断（内联） ---
                    if stock_code in stock_portfolio.positions:
                        pm = stock_portfolio.positions[stock_code]
                        if not pm.is_empty() and pm.entry_ma120 is not None:
                            ma120_ref = pm.entry_ma120
                            for i, (ratio, fund_ratio) in enumerate(strategy.ladder_down):
                                if i == 0 or pm.has_layer(i):
                                    continue
                                if current_price <= ma120_ref * ratio:
                                    amount = strategy.calculate_position_size(100000, fund_ratio, current_price)
                                    extra = self._get_trade_extra_fast(date_str, stock_code, idx, df)
                                    stock_portfolio.buy(date_str, stock_code, stock_name, current_price,
                                                        amount, i, target_profit_rate=strategy.single_profit, **extra)

                # --- 快速入场判断（内联） ---
                if stock_code not in stock_portfolio.positions:
                    if current_ma120 is not None and not np.isnan(current_ma120):
                        threshold = current_ma120 * strategy.entry_threshold
                        if current_price <= threshold:
                            first_fund = strategy.ladder_down[0][1] if strategy.ladder_down else 0.1
                            amount = strategy.calculate_position_size(100000, first_fund, current_price)
                            extra = self._get_trade_extra_fast(date_str, stock_code, idx, df)
                            stock_portfolio.buy(date_str, stock_code, stock_name, current_price,
                                                amount, 0, current_ma120, target_profit_rate=strategy.single_profit, **extra)

            # 计算未完成交易盈亏
            last_date = trading_days[-1] if trading_days else None
            if last_date:
                last_end_idx = date_idx_map.get(last_date)
                if last_end_idx and last_end_idx > 0:
                    last_price = float(close_arr[last_end_idx - 1])
                    for trade in stock_portfolio.trades:
                        if trade['action'] == 'BUY':
                            has_sell = any(
                                t['action'] in ['SELL_LAYER', 'SELL_ALL'] and
                                t.get('buy_date') == trade['date'] and
                                t.get('layer_index') == trade['layer_index']
                                for t in stock_portfolio.trades
                            )
                            if not has_sell:
                                buy_price = trade['price']
                                shares = trade['shares']
                                trade['uncompleted_price'] = last_price
                                trade['uncompleted_profit'] = (last_price - buy_price) * shares
                                trade['uncompleted_profit_rate'] = (last_price - buy_price) / buy_price

            self.portfolio.trades.extend(stock_portfolio.trades)
            if stock_code in stock_portfolio.positions:
                self.portfolio.positions[stock_code] = stock_portfolio.positions[stock_code]

            if progress_callback:
                percent = int(40 + ((si + 1) / num_stocks) * 40)
                progress_callback(percent, f"已完成 {si + 1}/{num_stocks} 只股票")

        print("\n生成每日统计数据...")
        for date_str in trading_days:
            self.portfolio.daily_stats.append({
                'date': date_str,
                'cash': self.portfolio.initial_capital,
                'stock_value': 0,
                'total_value': self.portfolio.initial_capital,
                'return': 0,
                'positions_count': 0,
                'index_price': self.index_data.get(date_str),
                'stock_layers': {}
            })
    
    def _calculate_uncompleted_trades_pnl(self, last_date):
        """计算未完成交易在回测结束时的盈亏"""
        if not last_date:
            return
        
        # 获取最后一天的价格（使用索引缓存）
        last_prices = {}
        for stock_code in self.qualified_stocks:
            date_idx_map = self._date_index_cache.get(stock_code, {})
            end_idx = date_idx_map.get(last_date)
            
            if end_idx and end_idx > 0:
                df = self.stock_data[stock_code]
                last_prices[stock_code] = df.iloc[end_idx - 1]['close']
        
        # 更新未完成买入的盈亏
        for trade in self.portfolio.trades:
            if trade['action'] == 'BUY':
                stock_code = trade['stock_code']
                buy_date = trade['date']
                layer_index = trade['layer_index']
                
                # 检查是否有对应的卖出
                has_sell = any(
                    t['action'] in ['SELL_LAYER', 'SELL_ALL'] and
                    t.get('buy_date') == buy_date and
                    t.get('layer_index') == layer_index
                    for t in self.portfolio.trades
                )
                
                # 如果未完成，计算当前盈亏
                if not has_sell and stock_code in last_prices:
                    current_price = last_prices[stock_code]
                    buy_price = trade['price']
                    shares = trade['shares']
                    
                    # 计算盈亏
                    profit_amount = (current_price - buy_price) * shares
                    profit_rate = (current_price - buy_price) / buy_price
                    
                    # 添加到交易记录中
                    trade['uncompleted_price'] = current_price  # 回测结束时价格
                    trade['uncompleted_profit'] = profit_amount  # 未实现盈亏
                    trade['uncompleted_profit_rate'] = profit_rate  # 未实现收益率
    
    def _get_data_until_date(self, stock_code, date_str):
        """获取某只股票到指定日期的数据（使用索引缓存，性能优化）"""
        if stock_code not in self.stock_data:
            return None
        
        df = self.stock_data[stock_code]
        date_idx_map = self._date_index_cache.get(stock_code, {})
        end_idx = date_idx_map.get(date_str)
        
        if end_idx is None:
            return None
        
        return df.iloc[:end_idx]
    
    def _process_day(self, date_str):
        """处理单个交易日"""
        current_prices = {}
        
        # 第一步：收集当日所有股票价格（使用索引缓存）
        for stock_code in self.qualified_stocks:
            date_idx_map = self._date_index_cache.get(stock_code, {})
            end_idx = date_idx_map.get(date_str)
            
            if end_idx and end_idx > 0:
                df = self.stock_data[stock_code]
                current_prices[stock_code] = df.iloc[end_idx - 1]['close']
        
        # 第二步：检查现有持仓的止盈信号
        for stock_code in list(self.portfolio.positions.keys()):
            df_until_today = self._get_data_until_date(stock_code, date_str)
            
            if df_until_today is None or len(df_until_today) < 120:
                continue
            
            pm = self.portfolio.positions[stock_code]
            current_price = current_prices.get(stock_code, None)
            
            if current_price is None:
                continue
            
            # 检查止盈信号
            is_full_clear, layers_to_sell, sell_reason = self.strategy.check_take_profit_signal(
                df_until_today, pm
            )
            
            if is_full_clear:
                extra = self._get_trade_extra(date_str, stock_code)
                extra['sell_reason'] = sell_reason
                self.portfolio.sell(date_str, stock_code, current_price, sell_all=True, **extra)
            else:
                for layer_idx in layers_to_sell:
                    extra = self._get_trade_extra(date_str, stock_code)
                    extra['sell_reason'] = sell_reason
                    self.portfolio.sell(date_str, stock_code, current_price, 
                                      layer_index=layer_idx, **extra)
        
        # 第三步：检查现有持仓的加仓信号
        for stock_code in list(self.portfolio.positions.keys()):
            df_until_today = self._get_data_until_date(stock_code, date_str)
            
            if df_until_today is None or len(df_until_today) < 120:
                continue
            
            pm = self.portfolio.positions[stock_code]
            current_price = current_prices.get(stock_code, None)
            
            if current_price is None:
                continue
            
            # 检查加仓信号
            add_signals = self.strategy.check_add_position_signal(df_until_today, pm)
            
            for layer_idx, target_price, fund_ratio in add_signals:
                # 计算加仓金额（每只股票独立10万资金）
                per_stock_allocation = 100000
                amount = self.strategy.calculate_position_size(
                    per_stock_allocation, fund_ratio, current_price
                )
                
                # 执行加仓
                stock_name = self._lookup_stock_name(stock_code)
                extra = self._get_trade_extra(date_str, stock_code)
                
                self.portfolio.buy(
                    date_str, stock_code, stock_name, current_price, 
                    amount, layer_idx, target_profit_rate=self.strategy.single_profit, **extra
                )
        
        # 第四步：检查新的入场机会
        # 如果忽略持仓限制（用户选股/条件选股），则不检查max_positions
        can_open_new = self.ignore_max_positions or len(self.portfolio.positions) < self.max_positions
        
        if can_open_new:
            for stock_code in self.qualified_stocks:
                # 跳过已持仓的股票
                if stock_code in self.portfolio.positions:
                    continue
                
                df_until_today = self._get_data_until_date(stock_code, date_str)
                
                if df_until_today is None or len(df_until_today) < 120:
                    continue
                
                current_price = current_prices.get(stock_code, None)
                if current_price is None:
                    continue
                
                # 检查入场信号
                is_entry, entry_price, ma120_ref, layer_idx = \
                    self.strategy.check_entry_signal(df_until_today, None, stock_code)
                
                if is_entry:
                    # 计算首次入场金额（每只股票独立10万资金，使用梯级第一层配置）
                    per_stock_allocation = 100000
                    # 使用 LADDER_DOWN 第一层的 fund_ratio，而不是独立的 first_position_ratio
                    first_layer_fund_ratio = self.strategy.ladder_down[0][1] if self.strategy.ladder_down else 0.1
                    amount = self.strategy.calculate_position_size(
                        per_stock_allocation, 
                        first_layer_fund_ratio, 
                        current_price
                    )
                    
                    # 执行入场
                    stock_name = self._lookup_stock_name(stock_code)
                    extra = self._get_trade_extra(date_str, stock_code)
                    
                    success = self.portfolio.buy(
                        date_str, stock_code, stock_name, current_price, 
                        amount, layer_idx, ma120_ref, target_profit_rate=self.strategy.single_profit, **extra
                    )
                    
                    # 只有在不忽略持仓限制时才检查
                    if success and not self.ignore_max_positions and len(self.portfolio.positions) >= self.max_positions:
                        break
        
        # 第五步：记录每日统计
        index_price = self.index_data.get(date_str)
        self.portfolio.record_daily_stats(date_str, current_prices, index_price)
    
    def analyze_results(self):
        """分析回测结果"""
        print("\n=== 第三阶段：分析结果 ===")
        
        trades_df = self.portfolio.get_trades_df()
        daily_stats_df = self.portfolio.get_daily_stats_df()
        
        if len(trades_df) == 0:
            print("没有产生任何交易")
            overall_stats = {}
            if daily_stats_df is not None and len(daily_stats_df) > 0:
                # 即使没有交易，也基于每日权益给出整体统计，方便前端展示
                overall_stats = self._calculate_overall_stats(daily_stats_df, trades_df)
            # 即使没有交易，也输出每只股票的指标行（全为0/或基于已有数据计算）
            stock_results = self._analyze_by_stock(trades_df)
            # 返回一个空但结构完整的结果，避免上层 NoneType 错误
            empty_results = {
                'trades': trades_df,
                'daily_stats': daily_stats_df,
                'stock_results': stock_results,
                'overall_stats': overall_stats,
            }
            self.results = empty_results
            return empty_results
        
        print(f"\n总交易次数: {len(trades_df)}")
        print(f"买入次数: {len(trades_df[trades_df['action'] == 'BUY'])}")
        print(f"卖出次数: {len(trades_df[trades_df['action'].isin(['SELL_LAYER', 'SELL_ALL'])])}")
        
        # 统计有交易的股票数量
        traded_stocks = trades_df['stock_code'].unique() if len(trades_df) > 0 else []
        print(f"产生交易的股票数: {len(traded_stocks)}/{len(self.qualified_stocks)}")
        
        # 按股票显示交易数量
        if len(traded_stocks) > 0 and len(traded_stocks) <= 20:
            print("\n各股票交易数量:")
            for code in traded_stocks:
                stock_trades = trades_df[trades_df['stock_code'] == code]
                buy_count = len(stock_trades[stock_trades['action'] == 'BUY'])
                sell_count = len(stock_trades[stock_trades['action'].isin(['SELL_LAYER', 'SELL_ALL'])])
                name = self._lookup_stock_name(code)
                print(f"  {name}({code}): {len(stock_trades)}笔 (买{buy_count}/卖{sell_count})")
        
        # 按股票统计
        stock_results = self._analyze_by_stock(trades_df)
        
        # 整体统计
        overall_stats = self._calculate_overall_stats(daily_stats_df, trades_df)
        
        # 计算聚合交易统计（完成、未完成、完成率）
        total_completed = int(stock_results['完成交易'].sum()) if len(stock_results) > 0 else 0
        total_uncompleted = int(stock_results['未完成交易'].sum()) if len(stock_results) > 0 else 0
        total_all = total_completed + total_uncompleted
        completion_rate = f"{(total_completed / total_all):.2%}" if total_all > 0 else "0.00%"
        
        # 计算所有股票的平均指标
        avg_drawdown = 0.0
        avg_return = 0.0
        avg_holding_days = 0.0
        
        if len(stock_results) > 0:
            # 从百分比字符串中提取数值并计算平均值
            drawdown_values = []
            return_values = []
            holding_values = []
            
            for _, row in stock_results.iterrows():
                # 解析最大回撤（例如 "-12.34%" -> -0.1234）
                dd_str = row['最大回撤']
                if isinstance(dd_str, str) and '%' in dd_str:
                    try:
                        drawdown_values.append(float(dd_str.replace('%', '')) / 100)
                    except:
                        pass
                
                # 解析总收益率（例如 "25.67%" -> 0.2567）
                ret_str = row['总收益率']
                if isinstance(ret_str, str) and '%' in ret_str:
                    try:
                        return_values.append(float(ret_str.replace('%', '')) / 100)
                    except:
                        pass
                
                # 解析平均时间（例如 "45天" -> 45）
                time_str = row['平均时间']
                if isinstance(time_str, str) and '天' in time_str:
                    try:
                        holding_values.append(float(time_str.replace('天', '')))
                    except:
                        pass
            
            # 计算平均值
            if drawdown_values:
                avg_drawdown = sum(drawdown_values) / len(drawdown_values)
            if return_values:
                avg_return = sum(return_values) / len(return_values)
            if holding_values:
                avg_holding_days = sum(holding_values) / len(holding_values)
        
        overall_stats.update({
            '完成': total_completed,
            '未完成': total_uncompleted,
            '完成率': completion_rate,
            '平均回撤': f"{avg_drawdown:.2%}",
            '平均收益率': f"{avg_return:.2%}",
            '平均耗时': f"{avg_holding_days:.0f}天"
        })
        
        self.results = {
            'trades': trades_df.to_dict('records') if len(trades_df) > 0 else [],
            'daily_stats': daily_stats_df.to_dict('records') if daily_stats_df is not None else [],
            'stock_results': stock_results.to_dict('records') if len(stock_results) > 0 else [],
            'overall_stats': overall_stats,
        }
        
        return self.results
    
    def _analyze_by_stock(self, trades_df):
        """按股票分析"""
        # 目标：每次回测都返回“所选股票列表”的完整表格
        # - 即使某只股票没有产生卖出交易，也输出一行（各指标为0）

        # trades_df 可能为空；为了统一处理，这里总是构造一个 dataframe
        if trades_df is None:
            trades_df = pd.DataFrame()

        # 以本次入池股票为准（用户手动选股时，qualified_stocks 即为可用价格数据的股票列表）
        codes = list(self.qualified_stocks or [])
        if not codes:
            return pd.DataFrame(columns=['股票', '代码', '总收益率', '最大回撤', '回测胜率', '交易次数', '盈亏比', '平均时间', '盈利耗时', '单笔均益', 'ATR%'])

        # 预分组：按股票汇总交易
        stock_trades = defaultdict(list)
        if len(trades_df) > 0 and 'stock_code' in trades_df.columns:
            for _, trade in trades_df.iterrows():
                stock_code = trade['stock_code']
                stock_trades[str(stock_code)] .append(trade)

        results = []

        for stock_code in codes:
            stock_code = str(stock_code)
            trades = stock_trades.get(stock_code, [])
            trades_df_stock = pd.DataFrame(trades) if trades else pd.DataFrame()

            stock_name = self._lookup_stock_name(stock_code)

            # BUY / SELL
            if len(trades_df_stock) > 0 and 'action' in trades_df_stock.columns:
                buy_trades = trades_df_stock[trades_df_stock['action'] == 'BUY']
                sell_trades = trades_df_stock[trades_df_stock['action'].isin(['SELL_LAYER', 'SELL_ALL'])]
            else:
                buy_trades = pd.DataFrame()
                sell_trades = pd.DataFrame()

            trade_count = int(len(sell_trades))

            # 胜率
            if trade_count > 0 and 'profit_amount' in sell_trades.columns:
                profitable_trades = sell_trades[sell_trades['profit_amount'] > 0]
                win_rate = len(profitable_trades) / trade_count
            else:
                profitable_trades = pd.DataFrame()
                win_rate = 0

            # 盈亏比（平均盈利 / 平均亏损绝对值）
            if trade_count > 0 and 'profit_amount' in sell_trades.columns:
                avg_profit = profitable_trades['profit_amount'].mean() if len(profitable_trades) > 0 else 0
                loss_trades = sell_trades[sell_trades['profit_amount'] < 0]
                avg_loss = abs(loss_trades['profit_amount'].mean()) if len(loss_trades) > 0 else 0
                profit_loss_ratio = (avg_profit / avg_loss) if avg_loss > 0 else 0
            else:
                profit_loss_ratio = 0

            # ---- 持仓时间统计 ----
            # 优先使用 sell trade 中的 holding_days 字段，回退到 layer_index 匹配
            all_holding_days = []
            profit_holding_days = []
            if trade_count > 0:
                for _, sell in sell_trades.iterrows():
                    days = None
                    # 方式1: 直接取 holding_days 字段
                    if 'holding_days' in sell.index and pd.notna(sell.get('holding_days')):
                        days = int(sell['holding_days'])
                    # 方式2: 通过 buy_date 计算
                    elif 'buy_date' in sell.index and pd.notna(sell.get('buy_date')):
                        try:
                            days = (pd.to_datetime(sell['date']) - pd.to_datetime(sell['buy_date'])).days
                        except Exception:
                            pass
                    # 方式3: 回退到 layer_index 匹配
                    if days is None and len(buy_trades) > 0 and 'layer_index' in sell.index:
                        layer_idx = sell.get('layer_index')
                        if layer_idx is not None:
                            buy = buy_trades[buy_trades['layer_index'] == layer_idx]
                            if len(buy) > 0:
                                try:
                                    days = (pd.to_datetime(sell['date']) - pd.to_datetime(buy.iloc[0]['date'])).days
                                except Exception:
                                    pass

                    if days is not None:
                        all_holding_days.append(days)
                        # 盈利交易的持仓天数
                        pa = sell.get('profit_amount', 0)
                        if pd.notna(pa) and float(pa) > 0:
                            profit_holding_days.append(days)

            avg_holding_days = float(np.mean(all_holding_days)) if all_holding_days else 0.0
            avg_profit_holding_days = float(np.mean(profit_holding_days)) if profit_holding_days else 0.0

            # 单笔均益（卖出交易 profit_amount 平均）
            if trade_count > 0 and 'profit_amount' in sell_trades.columns:
                avg_profit_per_trade = float(sell_trades['profit_amount'].mean())
            else:
                avg_profit_per_trade = 0.0

            # 总收益率 (相对于实际买入成本)
            # 计算实际买入成本 = sum(买入价 * 股数)
            if len(buy_trades) > 0 and 'price' in buy_trades.columns and 'shares' in buy_trades.columns:
                total_buy_cost = (buy_trades['price'] * buy_trades['shares']).sum()
            else:
                total_buy_cost = 0.0
            total_stock_profit = sell_trades['profit_amount'].sum() if len(sell_trades) > 0 else 0.0
            stock_yield = total_stock_profit / total_buy_cost if total_buy_cost > 0 else 0.0

            # 最大回撤（基于持仓期间股价的真实回撤）
            max_dd = self._calculate_stock_max_drawdown(stock_code, buy_trades, sell_trades)

            # ATR%（均值）
            if stock_code in self.stock_data and 'atr_percent' in self.stock_data[stock_code].columns:
                atr_percent = float(self.stock_data[stock_code]['atr_percent'].mean())
            else:
                atr_percent = 0.0

            # 获取当前持仓层数（未完成交易）
            holding_layers = 0
            if stock_code in self.portfolio.positions:
                holding_layers = len(self.portfolio.positions[stock_code].layers)

            results.append({
                '股票': stock_name,
                '代码': stock_code,
                '总收益率': f"{stock_yield:.2%}",
                '最大回撤': f"{max_dd:.2%}",
                '回测胜率': f"{win_rate:.2%}",
                '完成交易': trade_count,
                '未完成交易': holding_layers,
                '平均时间': f"{avg_holding_days:.0f}天",
                '单笔均益': f"{avg_profit_per_trade:.2f}",
            })

        return pd.DataFrame(results)
    
    def _calculate_stock_max_drawdown(self, stock_code, buy_trades, sell_trades):
        """
        计算单只股票的最大回撤 —— 基于持仓期间的股价变动。

        逻辑：
        1. 确定该股票的持仓期间（首次买入 → 最后卖出 或 回测结束）
        2. 在持仓期间，按日逐笔模拟持仓市值的变化
        3. 用「持仓成本 + 已实现盈亏」作为权益基线，跟踪峰值和回撤

        如果没有日线数据，回退到股价级别的 peak-to-trough 回撤。
        """
        if stock_code not in self.stock_data:
            return 0.0

        df = self.stock_data[stock_code]
        if len(df) == 0:
            return 0.0

        # 确定持仓区间
        all_dates = []
        if buy_trades is not None and len(buy_trades) > 0 and 'date' in buy_trades.columns:
            all_dates.extend(buy_trades['date'].tolist())
        if sell_trades is not None and len(sell_trades) > 0 and 'date' in sell_trades.columns:
            all_dates.extend(sell_trades['date'].tolist())

        if not all_dates:
            return 0.0

        # 将日期统一为字符串
        start_dt = min(pd.to_datetime(all_dates))
        end_dt = max(pd.to_datetime(all_dates))

        # 截取持仓期间的日线
        mask = (df['date'] >= start_dt) & (df['date'] <= end_dt)
        holding_df = df.loc[mask]

        if len(holding_df) == 0:
            return 0.0

        # 使用持仓期间的价格序列计算回撤
        close = holding_df['close'].values
        peak = close[0]
        max_dd = 0.0
        for p in close:
            if p > peak:
                peak = p
            if peak > 0:
                dd = (p - peak) / peak
                if dd < max_dd:
                    max_dd = dd

        return max_dd
    
    def _calculate_overall_stats(self, daily_stats_df, trades_df):
        """计算整体统计（移除冗余财务指标）"""
        stats = {}
        
        # 资金利用统计
        if daily_stats_df is not None and len(daily_stats_df) > 0:
            stock_vals = daily_stats_df['stock_value']
            stats['最大持仓市值'] = f"{stock_vals.max():,.2f}"
            stats['平均持仓市值'] = f"{stock_vals.mean():,.2f}"
            
        return stats
    
    def save_results(self, output_dir=OUTPUT_DIR):
        """保存回测结果"""
        import os
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存股票明细结果
        if 'stock_results' in self.results and len(self.results['stock_results']) > 0:
            stock_file = os.path.join(output_dir, f"stock_results_{timestamp}.xlsx")
            self.results['stock_results'].to_excel(stock_file, index=False)
            print(f"\n股票明细结果已保存: {stock_file}")
        
        # 保存交易记录
        if SAVE_TRADES and 'trades' in self.results and len(self.results['trades']) > 0:
            trades_file = os.path.join(output_dir, f"trades_{timestamp}.xlsx")
            self.results['trades'].to_excel(trades_file, index=False)
            print(f"交易记录已保存: {trades_file}")
        
        # 保存每日统计
        if SAVE_DAILY_POSITIONS and 'daily_stats' in self.results:
            daily_file = os.path.join(output_dir, f"daily_stats_{timestamp}.xlsx")
            self.results['daily_stats'].to_excel(daily_file, index=False)
            print(f"每日统计已保存: {daily_file}")
        
        # 保存整体统计
        if 'overall_stats' in self.results:
            overall_file = os.path.join(output_dir, f"overall_stats_{timestamp}.txt")
            with open(overall_file, 'w', encoding='utf-8') as f:
                f.write("=== 回测整体统计 ===\n\n")
                for key, value in self.results['overall_stats'].items():
                    f.write(f"{key}: {value}\n")
            print(f"整体统计已保存: {overall_file}")
    
    def print_summary(self):
        """打印回测摘要"""
        if 'overall_stats' not in self.results:
            return
        
        print("\n" + "="*60)
        print("回测摘要")
        print("="*60)
        
        for key, value in self.results['overall_stats'].items():
            print(f"{key:12s}: {value}")
        
        print("="*60)
        
        # 打印股票结果表格
        if 'stock_results' in self.results and len(self.results['stock_results']) > 0:
            print("\n股票明细结果:")
            stock_res = self.results['stock_results']
            if isinstance(stock_res, list):
                print(pd.DataFrame(stock_res).to_string(index=False))
            else:
                print(stock_res.to_string(index=False))
