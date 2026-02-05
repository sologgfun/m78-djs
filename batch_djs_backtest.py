#!/usr/bin/env python3
"""
点金术批量回测脚本

功能：
1. 使用 pywencai 筛选符合点金术条件的股票（PE<20, 股息率>3%, 价格<120日均线*90%）
2. 对筛选出的股票进行2024年全年回测
3. 结果保存到回测系统数据库

使用方法：
    python batch_djs_backtest.py

配置参数：
    - PE_MAX: PE(TTM) 上限，默认20
    - DIVIDEND_MIN: 股息率下限(%)，默认3
    - PRICE_RATIO_MAX: 价格/120日均线最大比例(%)，默认90
    - START_DATE: 回测开始日期
    - END_DATE: 回测结束日期
    - FIRST_POSITION: 首次仓位金额，默认10000元
"""

import sys
import os
import uuid
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

import pywencai
import pandas as pd

from backtest_engine import BacktestEngine
from backend.database import Database
from config import LADDER_DOWN, SINGLE_LAYER_PROFIT, FULL_CLEAR_THRESHOLD


# ==================== 配置参数 ====================
PE_MAX = 20                    # PE(TTM) 上限
DIVIDEND_MIN = 3               # 股息率下限(%)
# 注意：价格/120日均线 是入场信号条件，不是筛选条件

START_DATE = "2022-01-01"      # 回测开始日期
END_DATE = "2022-12-31"        # 回测结束日期

INITIAL_CAPITAL = 10_000_000_000  # 初始资金100亿（模拟无限资金）
MAX_POSITIONS = 999            # 不限制持仓数

# 梯级仓位金额（绝对金额，单位：元）
# 格式：[(阈值比例, 仓位金额), ...]
# 阈值比例：相对于120日均线的比例，触发买入
LADDER_AMOUNTS = [
    (0.88, 10000),   # MA120 * 88%，首次仓位1万
    (0.80, 20000),   # MA120 * 80%，加仓2万
    (0.70, 30000),   # MA120 * 70%，加仓3万
    (0.60, 40000),   # MA120 * 60%，加仓4万
]


def screen_djs_stocks(pe_max=PE_MAX, dividend_min=DIVIDEND_MIN):
    """
    使用 pywencai 筛选符合点金术基本面条件的股票
    
    条件：
    - PE(TTM) < pe_max
    - 股息率(近12个月) > dividend_min%
    
    注意：价格/120日均线 是入场信号，不是筛选条件
    """
    print(f"正在筛选符合点金术条件的股票...")
    print(f"  PE(TTM) < {pe_max}")
    print(f"  股息率 > {dividend_min}%")
    
    query = (
        f"市盈率(ttm)<{pe_max}，"
        f"市盈率(ttm)>0，"
        f"股息率(近12个月)>{dividend_min}，"
        f"非ST，非停牌"
    )
    
    try:
        res = pywencai.get(question=query, query_type='stock', loop=True)
        
        df = None
        if res is not None:
            if isinstance(res, pd.DataFrame):
                df = res
            elif isinstance(res, dict):
                for k, v in res.items():
                    if isinstance(v, pd.DataFrame):
                        df = v
                        break
        
        if df is None or len(df) == 0:
            print("未找到符合条件的股票")
            return []
        
        # 提取股票代码
        code_col = None
        for col in df.columns:
            if '股票代码' in col:
                code_col = col
                break
        
        if code_col is None:
            print("无法找到股票代码列")
            return []
        
        codes = df[code_col].dropna().unique().tolist()
        # 清理代码格式（去除后缀如 .SH, .SZ）
        codes = [str(c).split('.')[0] for c in codes]
        
        print(f"筛选完成，共找到 {len(codes)} 只符合条件的股票")
        return codes
        
    except Exception as e:
        print(f"筛选股票时出错: {e}")
        return []


def run_batch_backtest(stock_codes, start_date=START_DATE, end_date=END_DATE,
                       initial_capital=INITIAL_CAPITAL, 
                       max_positions=MAX_POSITIONS):
    """
    对股票列表进行批量回测
    """
    if not stock_codes:
        print("股票列表为空，跳过回测")
        return None
    
    print(f"\n开始回测...")
    print(f"  股票数量: {len(stock_codes)}")
    print(f"  回测区间: {start_date} ~ {end_date}")
    print(f"  梯级仓位: {[amt for _, amt in LADDER_AMOUNTS]} 元")
    
    # 将固定金额转换为资金比例（金额/初始资本）
    # 这样可以复用现有策略的 LADDER_DOWN 格式
    ladder_down_ratios = [
        (threshold, amount / initial_capital) 
        for threshold, amount in LADDER_AMOUNTS
    ]
    
    # 首次入场比例
    first_position_ratio = LADDER_AMOUNTS[0][1] / initial_capital
    
    # 构建策略配置
    config = {
        'LADDER_DOWN': ladder_down_ratios,
        'FIRST_POSITION_RATIO': first_position_ratio,
        'single_layer_profit': SINGLE_LAYER_PROFIT,
        'FULL_CLEAR_THRESHOLD': FULL_CLEAR_THRESHOLD,
    }
    
    # 创建回测引擎
    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        max_positions=max_positions,
        config=config
    )
    
    # 加载数据
    print("加载股票数据...")
    engine.load_data(stock_codes=stock_codes)
    
    # 执行回测
    print("执行回测...")
    engine.run()
    
    # 分析结果
    print("分析结果...")
    engine.analyze_results()
    
    return engine


def save_to_database(engine, stock_codes, task_name="DJS批量回测"):
    """
    将回测结果保存到数据库
    """
    print("\n保存结果到数据库...")
    
    db = Database()
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    batch_id = f"djs_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 构建任务信息
    task = {
        'task_id': task_id,
        'batch_id': batch_id,
        'name': task_name,
        'stock_codes': stock_codes,
        'start_date': engine.start_date,
        'end_date': engine.end_date,
        'initial_capital': engine.initial_capital if engine.initial_capital != float('inf') else 999999999,
        'max_positions': engine.max_positions,
        'config_type': 'custom',
        'status': 'completed',
        'progress': 100,
        'message': f'回测完成，共 {len(stock_codes)} 只股票',
        'created_at': datetime.now().isoformat(),
        'started_at': datetime.now().isoformat(),
        'completed_at': datetime.now().isoformat(),
        'strategy': {
            'entry_threshold': 0.88, # 默认值，脚本中写死的
            'first_position_ratio': engine.strategy.first_position_ratio,
            'single_layer_profit': engine.strategy.single_layer_profit,
            'full_clear_threshold': engine.strategy.full_clear_threshold,
            'ladder_down': engine.strategy.ladder_down,
        }
    }
    
    db.save_task(task)
    
    # 构建结果
    results = {
        'overall_stats': engine.results.get('overall_stats', {}),
        'stock_results': engine.results.get('stock_results', []),
        'trades': engine.results.get('trades', []),
        'daily_stats': engine.results.get('daily_stats', []),
    }
    
    db.save_result(task_id, results)
    
    print(f"结果已保存，任务ID: {task_id}")
    return task_id


def main():
    """主函数"""
    print("=" * 60)
    print("点金术批量回测脚本")
    print("=" * 60)
    
    # 1. 筛选股票
    stock_codes = screen_djs_stocks()
    
    if not stock_codes:
        print("\n未找到符合条件的股票，退出")
        return
    
    print(f"\n符合条件的股票代码：")
    for i, code in enumerate(stock_codes[:20]):
        print(f"  {code}", end="  ")
        if (i + 1) % 5 == 0:
            print()
    if len(stock_codes) > 20:
        print(f"  ... 共 {len(stock_codes)} 只")
    print()
    
    # 2. 执行回测
    engine = run_batch_backtest(stock_codes)
    
    if engine is None:
        print("\n回测失败，退出")
        return
    
    # 3. 打印摘要
    try:
        engine.print_summary()
    except Exception as e:
        print(f"打印摘要时出错: {e}")
        # 手动打印基本信息
        stats = engine.results.get('overall_stats', {})
        print(f"\n总收益率: {stats.get('total_return', 0):.2%}")
        print(f"最大回撤: {stats.get('max_drawdown', 0):.2%}")
        print(f"总交易次数: {stats.get('total_trades', 0)}")
    
    # 4. 保存到数据库
    task_id = save_to_database(engine, stock_codes)
    
    print("\n" + "=" * 60)
    print(f"回测完成！任务ID: {task_id}")
    print("可在回测系统前端查看详细结果")
    print("=" * 60)


if __name__ == "__main__":
    main()
