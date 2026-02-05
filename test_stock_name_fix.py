#!/usr/bin/env python3
"""
测试股票名称获取修复
特别测试浦发银行等问题股票
"""
from data_fetcher import DataFetcher
from backtest_engine import BacktestEngine

def test_stock_name_fetching():
    print("\n" + "="*60)
    print("测试股票名称获取")
    print("="*60)
    
    # 测试股票列表
    test_stocks = [
        ("600000", "浦发银行"),
        ("000001", "平安银行"),
        ("600036", "招商银行"),
        ("601398", "工商银行"),
    ]
    
    fetcher = DataFetcher()
    
    print("\n[1/3] 测试单个获取基本面数据...")
    for code, expected_name in test_stocks:
        fund = fetcher.get_stock_fundamental(code)
        if fund:
            actual_name = fund.get('stock_name', '')
            status = "✓" if actual_name and actual_name != code else "✗"
            print(f"{status} {code}: {actual_name} (期望: {expected_name})")
        else:
            print(f"✗ {code}: 获取失败")
    
    print("\n[2/3] 测试批量获取基本面数据...")
    codes = [stock[0] for stock in test_stocks]
    df = fetcher.batch_get_fundamentals(codes)
    
    if df is not None and not df.empty:
        print(f"成功获取 {len(df)} 只股票")
        for code, expected_name in test_stocks:
            row = df[df['stock_code'] == code]
            if not row.empty:
                actual_name = row.iloc[0]['stock_name']
                # 检查是否为空或无效
                is_valid = actual_name and isinstance(actual_name, str) and actual_name.strip() and actual_name != code
                status = "✓" if is_valid else "✗"
                print(f"{status} {code}: '{actual_name}' (期望: {expected_name})")
            else:
                print(f"✗ {code}: 未找到")
    else:
        print("✗ 批量获取失败")
    
    print("\n[3/3] 测试回测引擎名称映射...")
    engine = BacktestEngine(
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=100000,
        max_positions=2
    )
    
    # 加载数据时会构建 name_map
    engine.load_data(stock_codes=codes)
    
    print("\n名称映射表内容:")
    for code, expected_name in test_stocks:
        actual_name = engine.name_map.get(code, "")
        is_valid = actual_name and actual_name != code
        status = "✓" if is_valid else "✗"
        print(f"{status} {code} → '{actual_name}' (期望: {expected_name})")
    
    print("\n使用 _lookup_stock_name 方法:")
    for code, expected_name in test_stocks:
        actual_name = engine._lookup_stock_name(code)
        is_valid = actual_name and actual_name != code
        status = "✓" if is_valid else "✗"
        print(f"{status} {code} → '{actual_name}' (期望: {expected_name})")

def main():
    test_stock_name_fetching()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n如果所有股票都显示 ✓，说明名称获取功能正常")
    print("如果有 ✗，说明该股票的名称获取仍有问题")

if __name__ == "__main__":
    main()
