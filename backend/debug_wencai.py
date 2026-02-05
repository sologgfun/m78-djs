import sys
import os
import pywencai
import pandas as pd

def debug():
    query = "股票代码在(600519)中，市盈率(ttm)，股息率"
    print(f"Query: {query}")
    try:
        res = pywencai.get(question=query, query_type='stock', loop=True)
        print(f"Type: {type(res)}")
        if isinstance(res, dict):
            print("Keys:", res.keys())
            print("Content:", res)
        elif isinstance(res, pd.DataFrame):
            print("Columns:", res.columns)
            print("Head:", res.head())
        else:
            print("Unknown type")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug()
