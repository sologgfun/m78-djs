#!/usr/bin/env python3
"""
测试不同数据源获取历史数据的能力
"""
import sys
import akshare as ak
import pandas as pd
from datetime import datetime

def test_akshare_eastmoney():
    """测试 akshare 东财数据源"""
    print("\n" + "="*60)
    print("测试 akshare stock_zh_a_hist (东财数据源)")
    print("="*60)
    
    try:
        stock_code = "000001"  # 平安银行
        start_date = "20150101"
        end_date = "20251231"
        
        print(f"股票代码: {stock_code}")
        print(f"日期范围: {start_date} ~ {end_date}")
        print("正在获取数据...")
        
        df = ak.stock_zh_a_hist(
            symbol=stock_code, 
            period="daily", 
            start_date=start_date, 
            end_date=end_date, 
            adjust="qfq"
        )
        
        if df is not None and not df.empty:
            print(f"✓ 成功获取 {len(df)} 条数据")
            print(f"  日期范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
            print(f"  数据列: {list(df.columns)}")
            print("\n前5条:")
            print(df.head())
            print("\n后5条:")
            print(df.tail())
            return True, df
        else:
            print("✗ 返回数据为空")
            return False, None
            
    except Exception as e:
        print(f"✗ 获取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_akshare_sina():
    """测试 akshare 新浪数据源"""
    print("\n" + "="*60)
    print("测试 akshare stock_zh_a_daily (新浪数据源)")
    print("="*60)
    
    try:
        stock_code = "sz000001"  # 新浪格式
        
        print(f"股票代码: {stock_code}")
        print("正在获取数据...")
        
        df = ak.stock_zh_a_daily(
            symbol=stock_code,
            adjust="qfq"
        )
        
        if df is not None and not df.empty:
            print(f"✓ 成功获取 {len(df)} 条数据")
            print(f"  日期范围: {df.index[0]} ~ {df.index[-1]}")
            print(f"  数据列: {list(df.columns)}")
            print("\n前5条:")
            print(df.head())
            print("\n后5条:")
            print(df.tail())
            return True, df
        else:
            print("✗ 返回数据为空")
            return False, None
            
    except Exception as e:
        print(f"✗ 获取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_akshare_tushare():
    """测试 akshare Tushare 数据源（如果可用）"""
    print("\n" + "="*60)
    print("测试 akshare stock_zh_a_hist_163 (网易数据源)")
    print("="*60)
    
    try:
        stock_code = "0000001"  # 网易格式
        start_date = "20150101"
        end_date = "20251231"
        
        print(f"股票代码: {stock_code}")
        print(f"日期范围: {start_date} ~ {end_date}")
        print("正在获取数据...")
        
        df = ak.stock_zh_a_hist_163(
            symbol=stock_code,
            start_date=start_date,
            end_date=end_date,
        )
        
        if df is not None and not df.empty:
            print(f"✓ 成功获取 {len(df)} 条数据")
            print(f"  日期范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
            print(f"  数据列: {list(df.columns)}")
            print("\n前5条:")
            print(df.head())
            print("\n后5条:")
            print(df.tail())
            return True, df
        else:
            print("✗ 返回数据为空")
            return False, None
            
    except Exception as e:
        print(f"✗ 获取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def main():
    print("开始测试不同数据源...")
    print(f"当前 akshare 版本: {ak.__version__}")
    
    results = []
    
    # 测试东财
    success, df = test_akshare_eastmoney()
    results.append(("东财 (stock_zh_a_hist)", success, len(df) if df is not None else 0))
    
    # 测试新浪
    success, df = test_akshare_sina()
    results.append(("新浪 (stock_zh_a_daily)", success, len(df) if df is not None else 0))
    
    # 测试网易
    success, df = test_akshare_tushare()
    results.append(("网易 (stock_zh_a_hist_163)", success, len(df) if df is not None else 0))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    for name, success, count in results:
        status = "✓" if success else "✗"
        print(f"{status} {name}: {'成功' if success else '失败'} ({count} 条数据)")
    
    print("\n建议:")
    successful = [r for r in results if r[1]]
    if successful:
        best = max(successful, key=lambda x: x[2])
        print(f"推荐使用: {best[0]} ({best[2]} 条数据)")
    else:
        print("所有数据源均失败，建议检查网络连接或 akshare 版本")

if __name__ == "__main__":
    main()
