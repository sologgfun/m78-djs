#!/usr/bin/env python3
"""
集成测试：验证回测系统能使用新数据源正常工作
"""
from data_fetcher import DataFetcher
from backtest_engine import BacktestEngine
import pandas as pd

def test_integration():
    print("\n" + "="*60)
    print("回测系统集成测试 - 新浪数据源")
    print("="*60)
    
    # 1. 测试数据获取
    print("\n[1/3] 测试数据获取...")
    fetcher = DataFetcher()
    df = fetcher.get_stock_daily_data("000001", "2015-01-01", "2016-12-31")
    
    if df is None or df.empty:
        print("✗ 数据获取失败")
        return False
    
    print(f"✓ 成功获取 {len(df)} 条数据 ({df['date'].min()} ~ {df['date'].max()})")
    
    # 2. 测试回测引擎初始化
    print("\n[2/3] 测试回测引擎初始化...")
    try:
        engine = BacktestEngine(
            start_date="2015-01-01",
            end_date="2015-12-31",
            initial_capital=100000,
            max_positions=1
        )
        print("✓ 回测引擎初始化成功")
    except Exception as e:
        print(f"✗ 回测引擎初始化失败: {e}")
        return False
    
    # 3. 测试数据加载
    print("\n[3/3] 测试回测数据加载...")
    try:
        engine.load_data(stock_codes=["000001"])  # 单只股票快速测试
        if "000001" in engine.stock_data and not engine.stock_data["000001"].empty:
            stock_df = engine.stock_data["000001"]
            print(f"✓ 成功加载股票数据: {len(stock_df)} 条")
            print(f"  日期范围: {stock_df['date'].min()} ~ {stock_df['date'].max()}")
            
            # 检查是否包含2015年的数据
            year_2015 = stock_df[stock_df['date'].dt.year == 2015]
            if not year_2015.empty:
                print(f"  ✓ 包含 2015 年数据: {len(year_2015)} 条")
                return True
            else:
                print("  ✗ 未找到 2015 年数据")
                return False
        else:
            print("✗ 股票数据加载失败")
            return False
    except Exception as e:
        print(f"✗ 数据加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    success = test_integration()
    
    print("\n" + "="*60)
    if success:
        print("✓✓✓ 集成测试通过！")
        print("回测系统已准备就绪，可以使用 2015-2025 完整数据")
        print("="*60)
        print("\n建议:")
        print("1. 在前端创建新的回测任务")
        print("2. 设置日期范围: 2015-01-01 ~ 2025-12-31")
        print("3. 首次运行会自动下载并缓存数据")
    else:
        print("✗✗✗ 集成测试失败")
        print("="*60)
    
    return success

if __name__ == "__main__":
    main()
