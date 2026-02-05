import akshare as ak
import pandas as pd

try:
    print("Fetching 600519 (Moutai) via akshare...")
    # stock_zh_a_hist: 东方财富网-行情中心-沪深京A股-日行情
    df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20220101", end_date="20221231", adjust="qfq")
    print("Success!")
    print(df.tail())
except Exception as e:
    print(f"Failed: {e}")
