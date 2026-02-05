import subprocess as _sp
import json as _js
import uuid as _uuid

def load_index_data(start_date, end_date):
    """
    加载上证指数日线数据
    上证指数 Eastmoney secid = 1.000001
    """
    beg = start_date.replace("-", "")
    end = end_date.replace("-", "")
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&secid=1.000001"
        f"&beg={beg}&end={end}&klt=101&fqt=1"
        f"&ut=7eea3edcaed734bea9cbfc24409ed989"
    )
    print(f"URL: {url}")
    
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    cookies = f"qgqp_b_id={_uuid.uuid4().hex}; nid18={_uuid.uuid4().hex}"
    print(f"Cookies: {cookies}")
    
    cmd = [
        "/usr/bin/curl", "-4", "-s", "-S",
        "--max-time", "15", "--compressed",
        "-H", f"User-Agent: {ua}",
        "-H", "Accept: */*",
        "-b", cookies,
        url,
    ]
    try:
        result = _sp.run(cmd, capture_output=True, text=True, timeout=20)
        print(f"Return Code: {result.returncode}")
        
        if result.returncode != 0:
            print(f"Error Output: {result.stderr}")
            return
            
        if not result.stdout.strip():
            print("Empty stdout")
            return

        print(f"Response: {result.stdout[:200]}...")    
        data = _js.loads(result.stdout).get("data", {})
        if not data:
            print("No 'data' field in response")
            print(result.stdout)
            return

        klines = data.get("klines", [])
        print(f"Fetched {len(klines)} lines")
        if klines:
            print(f"First line: {klines[0]}")
            print(f"Last line: {klines[-1]}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    load_index_data("2022-01-01", "2022-12-31")
