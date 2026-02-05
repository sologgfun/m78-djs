#!/usr/bin/env python3
"""
测试新的数据获取功能（新浪数据源）
"""
from data_fetcher import DataFetcher
import pandas as pd

def test_data_fetcher():
    print("\n" + "="*60)
    print("测试 DataFetcher - 新浪数据源")
    print("="*60)
    
    fetcher = DataFetcher()
    
    # 测试获取 2015-2025 年的数据
    stock_code = "000001"  # 平安银行
    start_date = "2015-01-01"
    end_date = "2025-12-31"
    
    print(f"\n股票代码: {stock_code}")
    print(f"日期范围: {start_date} ~ {end_date}")
    print("正在获取数据...")
    
    df = fetcher.get_stock_daily_data(stock_code, start_date, end_date)
    
    if df is not None and not df.empty:
        print(f"\n✓ 成功获取 {len(df)} 条数据")
        print(f"  实际日期范围: {df['date'].min()} ~ {df['date'].max()}")
        print(f"  数据列: {list(df.columns)}")
        print("\n前5条:")
        print(df.head())
        print("\n后5条:")
        print(df.tail())
        
        # 统计数据
        years = df['date'].dt.year.unique()
        print(f"\n包含的年份: {sorted(years)}")
        print(f"年份数量: {len(years)} 年")
        
        return True
    else:
        print("\n✗ 获取数据失败")
        return False

if __name__ == "__main__":
    success = test_data_fetcher()
    
    if success:
        print("\n" + "="*60)
        print("✓ 测试通过！新浪数据源工作正常")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ 测试失败")
        print("="*60)
