"""
回测工作线程
"""
import threading
import sys
import os
import queue
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest_engine import BacktestEngine
from example_config import get_config
import pandas as pd

logger = logging.getLogger(__name__)


class BacktestWorker(threading.Thread):
    """回测工作线程"""
    
    def __init__(self, task_queue, database):
        super().__init__(daemon=True)
        self.task_queue = task_queue
        self.database = database
        self.running = True
    
    def run(self):
        """运行工作线程"""
        print("回测工作线程已启动")
        
        while self.running:
            try:
                # 从队列获取任务（阻塞等待）
                task = self.task_queue.get(timeout=1)
                
                if task is None:
                    break
                
                # 执行回测
                self._execute_backtest(task)
                
                # 标记任务完成
                self.task_queue.task_done()
                
            except queue.Empty:
                # 队列为空是正常情况，降低为 debug 日志
                if self.running:
                    logger.debug("回测工作线程空闲，等待任务...")
            except Exception as e:
                if self.running:
                    print(f"工作线程错误: {e}")
                    import traceback
                    traceback.print_exc()
    
    def _execute_backtest(self, task):
        """执行回测任务"""
        task_id = task['task_id']
        
        try:
            # 更新状态为运行中
            self.database.update_task_status(
                task_id, 'running', 0, '正在初始化...'
            )
            
            # 获取配置：优先使用前端传入的自定义策略参数
            strategy_params = task.get('strategy')
            if strategy_params and isinstance(strategy_params, dict):
                config = self._build_config_from_strategy(strategy_params)
            else:
                config = get_config(task.get('config_type', 'balanced'))
            
            # 创建回测引擎
            engine = BacktestEngine(
                start_date=task['start_date'],
                end_date=task['end_date'],
                initial_capital=task['initial_capital'],
                max_positions=task['max_positions'],
                config=config
            )
            
            # 自动选股模式
            if task.get('mode') == 'auto_screen':
                self.database.update_task_status(
                    task_id, 'running', 5, '正在筛选...'
                )
                
                # 获取筛选参数
                screen_params = task.get('screen_params', {})
                screen_type = screen_params.get('screen_type', 'stock')
                
                from backend.stock_service import StockService
                stock_service = StockService()

                if screen_type == 'etf':
                    # ----- ETF 筛选：按领域关键词 -----
                    etf_keyword = screen_params.get('etf_keyword', '')
                    self.database.update_task_status(
                        task_id, 'running', 5, f'正在筛选 ETF（{etf_keyword or "全部"}）...'
                    )
                    screened_results = stock_service.screen_etfs(keyword=etf_keyword)
                else:
                    # ----- 股票筛选：按 PE / 股息率 / 市值 -----
                    pe_max = float(screen_params.get('pe_max', 20))
                    dividend_min = float(screen_params.get('dividend_min', 3))
                    market_cap_min = float(screen_params.get('market_cap_min', 0))
                    screened_results = stock_service.screen_stocks(
                        pe_max=pe_max, 
                        dividend_min=dividend_min,
                        market_cap_min=market_cap_min
                    )
                
                if not screened_results:
                    label = 'ETF' if screen_type == 'etf' else '股票'
                    raise Exception(f"筛选结果为空，未找到符合条件的{label}")
                
                # 兼容新旧格式：screen_stocks 现在返回 list[dict]，提取 code 列表
                if isinstance(screened_results[0], dict):
                    screened_codes = [item['code'] for item in screened_results]
                    # 将名称预存到 engine 可用的映射表中（后续 load_data 会用到）
                    task['_screen_name_map'] = {
                        item['code']: item.get('name', '') 
                        for item in screened_results if item.get('name')
                    }
                else:
                    screened_codes = screened_results
                
                print(f"自动筛选完成，共 {len(screened_codes)} 只股票")
                task['stock_codes'] = screened_codes
                task['_is_auto_screen'] = True  # 标记为条件选股模式
                
                # 更新任务中的股票列表 (可选: 是否保存回DB? 暂不需要，结果会包含)
            
            # 加载数据
            self.database.update_task_status(
                task_id, 'running', 10, '正在加载数据...'
            )
            
            stock_codes = task.get('stock_codes', [])
            if not stock_codes or len(stock_codes) == 0:
                # 如果没有指定股票，使用默认测试股票
                stock_codes = ['600036', '601318', '600519', '600900', '601088']
            
            print(f"任务 {task_id} 将回测 {len(stock_codes)} 只股票")
            # 传递是否为条件选股的标记
            is_auto_screen = task.get('_is_auto_screen', False)
            engine.load_data(stock_codes=stock_codes, is_auto_screen=is_auto_screen)
            
            # 如果是自动筛选模式，把筛选时获得的名称注入到引擎的 name_map 中
            screen_name_map = task.get('_screen_name_map')
            if screen_name_map:
                for code, name in screen_name_map.items():
                    if name and code not in engine.name_map:
                        engine.name_map[code] = name
            
            # 执行回测
            def progress_cb(percent, msg):
                self.database.update_task_status(task_id, 'running', percent, msg)
                
            engine.run(progress_callback=progress_cb)
            
            # 分析结果
            self.database.update_task_status(
                task_id, 'running', 80, '正在分析结果...'
            )
            
            results = engine.analyze_results()
            
            # 转换结果为可序列化格式
            serializable_results = self._prepare_results(results)
            
            # 保存结果
            self.database.save_result(task_id, serializable_results)
            
            # 更新状态为完成
            self.database.update_task_status(
                task_id, 'completed', 100, '回测完成'
            )
            
            print(f"✓ 任务 {task_id} 完成")
            
        except Exception as e:
            # 更新状态为失败
            self.database.update_task_status(
                task_id, 'failed', 0, f'回测失败: {str(e)}'
            )
            print(f"✗ 任务 {task_id} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    @staticmethod
    def _build_config_from_strategy(strategy):
        """
        将前端传入的自定义策略参数转换为回测引擎可用的 config 字典。

        前端传入格式：
        {
            "entry_threshold": 0.88,
            "first_position_ratio": 0.10,
            "ladder_down": [[0.88, 0.10], [0.80, 0.20], ...],
            "single_layer_profit": 0.12,
            "full_clear_threshold": 1.12
        }
        """
        config = {}

        if 'entry_threshold' in strategy:
            config['ENTRY_SIGNAL_THRESHOLD'] = float(strategy['entry_threshold'])

        if 'first_position_ratio' in strategy:
            config['FIRST_POSITION_RATIO'] = float(strategy['first_position_ratio'])

        if 'ladder_down' in strategy:
            config['LADDER_DOWN'] = [
                (float(level[0]), float(level[1]))
                for level in strategy['ladder_down']
                if isinstance(level, (list, tuple)) and len(level) >= 2
            ]

        if 'single_layer_profit' in strategy:
            config['SINGLE_LAYER_PROFIT'] = float(strategy['single_layer_profit'])

        if 'enable_ma120_full_clear' in strategy:
            config['ENABLE_MA120_FULL_CLEAR'] = bool(strategy['enable_ma120_full_clear'])

        if 'full_clear_threshold' in strategy:
            config['FULL_CLEAR_THRESHOLD'] = float(strategy['full_clear_threshold'])

        if 'dynamic_take_profit' in strategy:
            config['DYNAMIC_TAKE_PROFIT'] = bool(strategy['dynamic_take_profit'])

        if 'rsi_overbought' in strategy:
            config['RSI_OVERBOUGHT'] = float(strategy['rsi_overbought'])

        # 默认不使用 ATR 动态调整
        config.setdefault('USE_DYNAMIC_ATR', False)

        return config

    def _prepare_results(self, results):
        """准备可序列化的结果

        analyze_results() 可能返回 DataFrame 或已转换的 list[dict]，
        两种情况都要正确处理。
        """
        if results is None:
            return {
                'overall_stats': {},
                'stock_results': [],
                'trades': [],
                'daily_stats': [],
            }

        serializable = {}

        # 整体统计 (dict)
        if 'overall_stats' in results:
            serializable['overall_stats'] = results['overall_stats']

        # 股票结果
        if 'stock_results' in results:
            val = results['stock_results']
            if isinstance(val, pd.DataFrame):
                serializable['stock_results'] = val.to_dict('records')
            elif isinstance(val, list):
                serializable['stock_results'] = val
            else:
                serializable['stock_results'] = []

        # 交易记录
        if 'trades' in results:
            val = results['trades']
            if isinstance(val, pd.DataFrame):
                trades_df = val.copy()
                if 'date' in trades_df.columns:
                    trades_df['date'] = trades_df['date'].astype(str)
                serializable['trades'] = trades_df.to_dict('records')
            elif isinstance(val, list):
                serializable['trades'] = val
            else:
                serializable['trades'] = []

        # 每日统计
        if 'daily_stats' in results:
            val = results['daily_stats']
            if isinstance(val, pd.DataFrame):
                daily_df = val.copy()
                if 'date' in daily_df.columns:
                    daily_df['date'] = daily_df['date'].astype(str)
                serializable['daily_stats'] = daily_df.to_dict('records')
            elif isinstance(val, list):
                serializable['daily_stats'] = val
            else:
                serializable['daily_stats'] = []

        return serializable
    
    def stop(self):
        """停止工作线程"""
        self.running = False
        self.task_queue.put(None)  # 发送停止信号
