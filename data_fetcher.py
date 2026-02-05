"""
数据获取模块
基于 akshare 获取 A 股 + ETF/LOF 数据，不自己构造 HTTP 请求
参考文档: https://akshare.akfamily.xyz/data/stock/stock.html

支持:
- A 股 (沪深主板、中小板、创业板、科创板)
- 场内 ETF (上海/深圳各类 ETF，含宽基、行业、债券、跨境、商品等)
- 场内 LOF (上市开放式基金)

注意: macOS 上代理软件 (如 Clash) 常以 Network Extension 形式运行,
     Python requests 的 socket 连接不会被 Network Extension 拦截,
     而 macOS 原生 curl 会自动走系统代理/Network Extension。
     因此本模块在调用 akshare 之前, 会将 requests.get/post 底层
     替换为 curl subprocess 调用, 确保网络请求经过系统代理栈。
"""
import akshare as ak
import pandas as pd
import os
import re
import math
import subprocess
import json as _json
import uuid
from datetime import datetime
from contextlib import contextmanager
from urllib.parse import urlencode
import time

import requests as _requests
import requests.api as _requests_api


# ---------------------------------------------------------------------------
# curl-based HTTP adapter  —  解决 macOS Network Extension 代理 + 东财反爬
# ---------------------------------------------------------------------------

class _CurlResponse:
    """模拟 requests.Response，供 akshare 内部透明使用"""

    def __init__(self, status_code, content_bytes, url=""):
        self.status_code = status_code
        self.content = content_bytes
        self.text = content_bytes.decode("utf-8", errors="replace")
        self.encoding = "utf-8"
        self.url = url
        self.headers = {}
        self.ok = 200 <= status_code < 400

    def json(self, **kwargs):
        return _json.loads(self.text, **kwargs)

    def raise_for_status(self):
        if not self.ok:
            raise _requests.HTTPError(
                f"{self.status_code} for url: {self.url}", response=self
            )


# 会话级 cookie（同一个 _use_curl 上下文内所有请求复用）
_session_cookies = ""

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _curl_request(method, url, **kwargs):
    """
    用 macOS 原生 curl 替代 requests 发起 HTTP 请求。

    解决两个问题:
    1. macOS Network Extension 代理 (Clash TUN 等) 不拦截 Python socket，
       curl 走系统网络栈会自动被 Network Extension 接管。
    2. 东财 API 要求浏览器 User-Agent + cookies 才返回数据。
       自动生成随机 qgqp_b_id / nid18 cookie 即可通过东财反爬。
    """
    global _session_cookies

    params = kwargs.get("params")
    headers = kwargs.get("headers", {})
    timeout = kwargs.get("timeout") or 30

    # 拼接 query string
    if params:
        qs = urlencode(params, doseq=True)
        sep = "&" if "?" in url else "?"
        url = url + sep + qs

    # 东财域名统一改写:
    # 82.push2.eastmoney.com / push2.eastmoney.com → push2his.eastmoney.com
    # 前者走 IPv6 且反爬严格，后者随机 cookies 即可
    url = re.sub(
        r"https://(\d+\.)?push2\.eastmoney\.com/",
        "https://push2his.eastmoney.com/",
        url,
    )

    # ---------- 构建 curl 命令 ----------
    cmd = [
        "/usr/bin/curl",
        "-4",           # 强制 IPv4（东财部分子域如 82.push2 走 IPv6 不通）
        "-s", "-S",
        "--max-time", str(int(timeout)),
        "-w", "\n%{http_code}",
        "-X", method.upper(),
        "--compressed",
    ]

    cmd.extend(["-H", f"User-Agent: {_BROWSER_UA}"])
    cmd.extend(["-H", "Accept: */*"])
    cmd.extend(["-H", "sec-ch-ua-platform: \"macOS\""])

    # 东财域名需要 cookies 过反爬 (其他域名不需要)
    if "eastmoney.com" in url:
        cookies = _session_cookies or (
            f"qgqp_b_id={uuid.uuid4().hex}; nid18={uuid.uuid4().hex}"
        )
        cmd.extend(["-b", cookies])

    # 上交所需要 Referer
    if "sse.com.cn" in url:
        cmd.extend(["-H", "Referer: https://www.sse.com.cn/"])

    # 额外 headers
    if headers:
        for k, v in headers.items():
            if k.lower() in ("user-agent", "accept"):
                continue
            cmd.extend(["-H", f"{k}: {v}"])

    cmd.append(url)

    # ---------- 执行 ----------
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=timeout + 10,
        )
    except subprocess.TimeoutExpired as exc:
        raise _requests.ConnectionError(f"curl 超时: {url}") from exc

    raw = result.stdout
    idx = raw.rfind(b"\n")
    if idx >= 0:
        body = raw[:idx]
        code_str = raw[idx + 1:].strip()
    else:
        body = raw
        code_str = b"0"

    try:
        status_code = int(code_str)
    except ValueError:
        status_code = 0

    if result.returncode != 0 and status_code == 0:
        stderr_text = (result.stderr.decode("utf-8", errors="replace")
                       if result.stderr else "")
        raise _requests.ConnectionError(
            f"curl 失败 (exit={result.returncode}): {stderr_text[:300]}"
        )

    return _CurlResponse(status_code, body, url)


# ---------------------------------------------------------------------------
# 市场识别辅助函数 —— 统一处理 A 股 + ETF 的市场归属
# ---------------------------------------------------------------------------

def _get_market_code(code):
    """
    获取证券代码的东财 API 市场编号。
    Returns: 1 = SH (上交所), 0 = SZ (深交所)
    
    上交所: 6xxxxx(主板/科创板), 5xxxxx(上海ETF/LOF/封闭基金), 9xxxxx(B股)
    深交所: 0xxxxx(主板/中小板), 3xxxxx(创业板), 1xxxxx(深圳ETF/LOF/可转债), 2xxxxx(B股)
    """
    code = str(code).zfill(6)
    if code.startswith(('6', '5', '9')):
        return 1
    return 0


def _get_market_prefix(code):
    """
    获取证券代码的市场前缀 (新浪/腾讯 API 使用)。
    Returns: 'sh' 或 'sz'
    """
    code = str(code).zfill(6)
    if code.startswith(('6', '5', '9')):
        return 'sh'
    return 'sz'


def _get_market_label(code):
    """
    获取证券代码的市场标签。
    Returns: 'SH' 或 'SZ'
    """
    code = str(code).zfill(6)
    if code.startswith(('6', '5', '9')):
        return 'SH'
    return 'SZ'


def is_etf_code(code):
    """
    判断证券代码是否为 ETF / LOF（场内交易基金）。

    上海 ETF: 5xxxxx
        510xxx(宽基ETF), 511xxx(债券ETF), 512xxx(行业ETF),
        513xxx(跨境ETF), 515xxx/516xxx/517xxx/518xxx(主题ETF),
        560xxx/561xxx/562xxx/563xxx(新规ETF), 588xxx(科创板ETF)
    深圳 ETF: 159xxx
    深圳 LOF: 160xxx, 161xxx, 162xxx, 163xxx, 164xxx, 165xxx, 166xxx, 167xxx, 168xxx, 169xxx
    """
    code = str(code).zfill(6)
    if code.startswith('5'):
        return True
    if code.startswith('159'):
        return True
    if code.startswith(('160', '161', '162', '163', '164', '165', '166', '167', '168', '169')):
        return True
    return False


class DataFetcher:
    """数据获取器 - 基于 akshare，底层使用 curl 保证网络连通"""
    
    def __init__(self, cache_dir="./data_cache", use_cache=True):
        self.cache_dir = cache_dir
        self.use_cache = use_cache
        
        # 创建缓存目录
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    @contextmanager
    def _use_curl(self):
        """
        上下文管理器: 将 requests 底层替换为 curl 实现。

        akshare 内部有两种调用方式:
        1. requests.get(url, ...) -> requests.api.request(...)
        2. requests.Session().get(url, ...) -> Session.request(...)

        两层都要 patch，确保所有请求都走 curl。
        会话内所有请求复用同一组 cookies，避免被东财检测为异常。
        """
        global _session_cookies

        original_api_request = _requests_api.request
        original_session_request = _requests.Session.request

        # 为本次会话生成一组固定的 cookies
        _session_cookies = (
            f"qgqp_b_id={uuid.uuid4().hex}; "
            f"nid18={uuid.uuid4().hex}; "
            f"nid18_create_time={int(time.time() * 1000)}"
        )

        def patched_api_request(method, url, **kwargs):
            return _curl_request(method, url, **kwargs)

        def patched_session_request(self_session, method, url, **kwargs):
            return _curl_request(method, url, **kwargs)

        _requests_api.request = patched_api_request
        _requests.Session.request = patched_session_request
        try:
            yield
        finally:
            _requests_api.request = original_api_request
            _requests.Session.request = original_session_request
            _session_cookies = ""
    
    def _fetch_stock_list_eastmoney(self):
        """
        从东财 clist/get 获取全部 A 股列表。
        注意：
        1. 该 API 必须用 push2.eastmoney.com（push2his 不支持 clist）
        2. 服务端限制每页最多 100 条，需要逐页分页
        3. push2 域名只能发 qgqp_b_id 一个 cookie（加 nid18 会被拒绝连接）
        4. 按市场分别获取以降低单次请求压力并避免频率限制
        """
        all_items = []

        # 按市场分别获取（减少单次分页数，避免频率限制）
        markets = [
            ("沪市主板", "m:1+t:2"),
            ("科创板", "m:1+t:23"),
            ("深市主板", "m:0+t:6"),
            ("深市中小板", "m:0+t:13"),
            ("创业板", "m:0+t:80"),
            # ETF / LOF
            ("上海ETF", "b:MK0021"),
            ("深圳ETF", "b:MK0022"),
            ("上海LOF", "b:MK0023"),
            ("深圳LOF", "b:MK0024"),
        ]

        for market_name, fs in markets:
            # 每个市场用新的 cookie 避免被关联限流
            cookies = f"qgqp_b_id={uuid.uuid4().hex}"
            page = 1
            market_count = 0

            while True:
                url = (
                    f"https://push2.eastmoney.com/api/qt/clist/get"
                    f"?pn={page}&pz=100&po=1&np=1&fltt=2"
                    f"&fields=f12,f14"
                    f"&fs={fs}"
                )
                cmd = [
                    "/usr/bin/curl", "-4", "-s", "-S",
                    "--max-time", "15", "--compressed",
                    "-H", f"User-Agent: {_BROWSER_UA}",
                    "-b", cookies,
                    url,
                ]

                success = False
                for attempt in range(3):
                    if attempt > 0:
                        time.sleep(1 + attempt)
                    try:
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=20
                        )
                        if result.returncode != 0 or not result.stdout.strip():
                            continue
                        data = _json.loads(result.stdout)
                        diff = data.get("data", {}).get("diff", [])
                        if not diff:
                            success = True  # 空页 = 结束
                            break
                        if isinstance(diff, dict):
                            diff = list(diff.values())
                        all_items.extend(diff)
                        market_count += len(diff)
                        total = data.get("data", {}).get("total", 0)
                        success = True
                        break
                    except Exception:
                        continue

                if not success or not diff:
                    break
                if market_count >= total:
                    break
                page += 1
                time.sleep(0.2)

            print(f"  {market_name}: {market_count} 只")
            time.sleep(0.5)  # 市场间间隔

        if not all_items:
            return pd.DataFrame()

        df = pd.DataFrame(all_items)
        df = df.rename(columns={"f12": "code", "f14": "name"})
        df["code"] = df["code"].astype(str).str.zfill(6)
        # 去重（ETF/LOF可能在多个板块中出现）
        df = df.drop_duplicates(subset=["code"], keep="first")
        df["market"] = df["code"].apply(_get_market_label)
        return df[["code", "name", "market"]]

    def get_stock_list(self):
        """
        获取A股股票列表

        优先使用 akshare，如果失败则直接调用东财 clist API。

        Returns:
        --------
        DataFrame : 包含 code, name, market 列
        """
        cache_file = os.path.join(self.cache_dir, "stock_list.csv")

        # A 股 + ETF 完整列表至少应包含此数量
        MIN_VALID_COUNT = 3000

        if self.use_cache and os.path.exists(cache_file):
            mod_time = os.path.getmtime(cache_file)
            mod_date = datetime.fromtimestamp(mod_time).date()
            if mod_date == datetime.now().date():
                df_cache = pd.read_csv(cache_file, dtype={"code": str})
                if "code" in df_cache.columns:
                    df_cache["code"] = df_cache["code"].astype(str).str.zfill(6)
                # 校验缓存完整性：数量不足说明是旧版残缺数据，需重新获取
                if len(df_cache) >= MIN_VALID_COUNT:
                    print(f"使用缓存的股票列表 ({len(df_cache)} 只)")
                    return df_cache
                else:
                    print(f"缓存数据不完整 ({len(df_cache)} 只 < {MIN_VALID_COUNT})，重新获取...")

        print("获取A股股票 + ETF 列表...")
        df = pd.DataFrame()

        # 方法 1: akshare 获取 A 股 + ETF
        try:
            with self._use_curl():
                df = ak.stock_info_a_code_name()
            if df is not None and len(df) > 0:
                if "code" in df.columns:
                    df["code"] = df["code"].astype(str).str.zfill(6)
                df["market"] = df["code"].apply(_get_market_label)
                if len(df) < MIN_VALID_COUNT:
                    print(f"  akshare 返回 {len(df)} 只，数量不足(需>{MIN_VALID_COUNT})，判定为不完整，改用备用方案")
                    df = pd.DataFrame()
                else:
                    # 补充 ETF 列表到 A 股列表中
                    etf_df = self._fetch_etf_list()
                    if etf_df is not None and len(etf_df) > 0:
                        df = pd.concat([df, etf_df], ignore_index=True)
                        df = df.drop_duplicates(subset=["code"], keep="first")
                        print(f"  合并 ETF 后共 {len(df)} 只证券")
        except Exception as e:
            print(f"  akshare 获取失败: {e}")
            df = pd.DataFrame()

        # 方法 2: 东财 clist API (备用，已包含 ETF 市场)
        if df is None or len(df) < MIN_VALID_COUNT:
            print("  使用东财 clist API 获取股票+ETF列表...")
            df = self._fetch_stock_list_eastmoney()

        if df is not None and len(df) > 0:
            # 只有结果合理时才写入缓存（避免不完整的数据覆盖旧缓存）
            if len(df) >= MIN_VALID_COUNT:
                df.to_csv(cache_file, index=False, encoding="utf-8-sig")
            else:
                print(f"  警告: 仅获取到 {len(df)} 只证券，不写入缓存")
            print(f"获取到 {len(df)} 只证券（含 ETF）")
            return df

        # 兜底: 使用过期缓存（网络不通时仍然可用）
        if os.path.exists(cache_file):
            try:
                df_old = pd.read_csv(cache_file, dtype={"code": str})
                if "code" in df_old.columns and len(df_old) > 0:
                    df_old["code"] = df_old["code"].astype(str).str.zfill(6)
                    print(f"使用过期的缓存数据 ({len(df_old)} 只)")
                    return df_old
            except Exception:
                pass
        return pd.DataFrame()
    
    def _fetch_etf_list(self):
        """
        获取场内 ETF/LOF 列表（带独立缓存）。
        缓存有效期 1 天，避免每次都走网络。
        """
        cache_file = os.path.join(self.cache_dir, "etf_list.csv")

        # ---------- 读缓存 ----------
        if self.use_cache and os.path.exists(cache_file):
            try:
                mod_time = os.path.getmtime(cache_file)
                mod_date = datetime.fromtimestamp(mod_time).date()
                if mod_date == datetime.now().date():
                    df_cache = pd.read_csv(cache_file, dtype={"code": str})
                    if "code" in df_cache.columns and len(df_cache) > 50:
                        df_cache["code"] = df_cache["code"].astype(str).str.zfill(6)
                        print(f"  使用缓存的 ETF 列表 ({len(df_cache)} 只)")
                        return df_cache
            except Exception:
                pass

        # ---------- 从网络获取 ----------
        try:
            with self._use_curl():
                df = ak.fund_etf_spot_em()
            if df is not None and len(df) > 0:
                # 列名: 代码, 名称, ...
                rename_map = {}
                for col in df.columns:
                    cl = str(col)
                    if cl == '代码':
                        rename_map[col] = 'code'
                    elif cl == '名称':
                        rename_map[col] = 'name'
                if 'code' not in rename_map.values():
                    for col in df.columns:
                        if 'code' in str(col).lower() or '代码' in str(col):
                            rename_map[col] = 'code'
                            break
                    for col in df.columns:
                        if 'name' in str(col).lower() or '名称' in str(col):
                            rename_map[col] = 'name'
                            break
                df = df.rename(columns=rename_map)
                if 'code' in df.columns:
                    df['code'] = df['code'].astype(str).str.zfill(6)
                    if 'name' not in df.columns:
                        df['name'] = ''
                    df['market'] = df['code'].apply(_get_market_label)
                    result = df[['code', 'name', 'market']]
                    # 写缓存
                    if len(result) > 50:
                        result.to_csv(cache_file, index=False, encoding="utf-8-sig")
                    print(f"  获取到 {len(result)} 只 ETF/LOF")
                    return result
        except Exception as e:
            print(f"  获取 ETF 列表失败: {e}")

        # ---------- 兜底：使用过期缓存 ----------
        if os.path.exists(cache_file):
            try:
                df_old = pd.read_csv(cache_file, dtype={"code": str})
                if "code" in df_old.columns and len(df_old) > 0:
                    df_old["code"] = df_old["code"].astype(str).str.zfill(6)
                    print(f"  使用过期的 ETF 缓存 ({len(df_old)} 只)")
                    return df_old
            except Exception:
                pass

        return pd.DataFrame()

    def _fetch_kline_etf(self, stock_code, start_date, end_date):
        """
        从东财获取 ETF 日线数据 (使用 akshare fund_etf_hist_em)。
        专门针对 ETF 代码，当通用股票接口无法获取 ETF 数据时作为后备。
        """
        try:
            s_date = start_date.replace("-", "")
            e_date = end_date.replace("-", "")

            with self._use_curl():
                df = ak.fund_etf_hist_em(
                    symbol=stock_code,
                    period="daily",
                    start_date=s_date,
                    end_date=e_date,
                    adjust="qfq"
                )

            if df is None or df.empty:
                return None

            # 重命名列
            rename_map = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount"
            }
            df = df.rename(columns=rename_map)

            required_cols = ["date", "open", "close", "high", "low", "volume", "amount"]
            if not all(col in df.columns for col in required_cols):
                return None

            df["date"] = pd.to_datetime(df["date"])
            return df[required_cols]
        except Exception as e:
            # print(f"  ETF 专用接口获取 {stock_code} 失败: {e}")
            return None

    def _fetch_kline_sina(self, stock_code, start_date, end_date):
        """
        从新浪获取日线数据 (使用 akshare stock_zh_a_daily)。
        新浪数据源稳定，支持从 1991 年至今的完整历史数据。
        也支持 ETF（新浪 API 统一使用 sh/sz 前缀）。
        """
        try:
            # 新浪格式需要市场前缀（支持 A 股 + ETF）
            sina_code = f"{_get_market_prefix(stock_code)}{stock_code}"
            
            # 使用 akshare 获取数据
            df = ak.stock_zh_a_daily(
                symbol=sina_code,
                adjust="qfq"
            )
            
            if df is None or df.empty:
                return None
                
            # 新浪返回的列名已经是英文
            # columns: date, open, high, low, close, volume, amount, outstanding_share, turnover
            
            # 确保包含所需列
            required_cols = ["date", "open", "close", "high", "low", "volume", "amount"]
            if not all(col in df.columns for col in required_cols):
                return None
                
            # 转换日期格式
            df["date"] = pd.to_datetime(df["date"])
            
            # 按日期范围过滤
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
            
            if df.empty:
                return None
            
            return df[required_cols].reset_index(drop=True)
            
        except Exception as e:
            # print(f"  新浪获取 {stock_code} 失败: {e}")
            return None

    def _fetch_kline_eastmoney(self, stock_code, start_date, end_date):
        """
        从东财获取日线数据 (使用 akshare stock_zh_a_hist)。
        替代原有的 manual curl 实现，提高稳定性和速度。
        """
        try:
            # 格式化日期 YYYYMMDD
            s_date = start_date.replace("-", "")
            e_date = end_date.replace("-", "")
            
            # 使用 akshare 获取数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code, 
                period="daily", 
                start_date=s_date, 
                end_date=e_date, 
                adjust="qfq"
            )
            
            if df is None or df.empty:
                return None
                
            # 重命名列以匹配原有格式
            # akshare columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...
            rename_map = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount"
            }
            df = df.rename(columns=rename_map)
            
            # 确保包含所需列
            required_cols = ["date", "open", "close", "high", "low", "volume", "amount"]
            if not all(col in df.columns for col in required_cols):
                return None
                
            # 转换日期格式 (YYYY-MM-DD), akshare 返回的日期通常已经是 YYYY-MM-DD 格式 (字符串或 date)
            df["date"] = pd.to_datetime(df["date"])
            
            return df[required_cols]
            
        except Exception as e:
            # Fallback will handle failure
            # print(f"  akshare 获取 {stock_code} 失败: {e}")
            return None

    def _fetch_kline_tencent(self, stock_code, start_date, end_date):
        """
        从腾讯获取日线数据 (备用数据源, 不含成交额)。
        成交额用典型价 × 成交量估算: amount ≈ (H+L+C)/3 × volume × 100
        支持 A 股 + ETF。
        """
        prefix = _get_market_prefix(stock_code)
        # 5000 条覆盖约 20 年交易日，确保 2015-2025 等长时间段有完整数据
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?_var=kline_dayqfq"
            f"&param={prefix}{stock_code},day,{start_date},{end_date},5000,qfq"
        )
        cmd = [
            "/usr/bin/curl", "-4", "-s", "-S",
            "--max-time", "15", "--compressed",
            "-H", f"User-Agent: {_BROWSER_UA}",
            url,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=20
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None

            text = re.sub(r"^kline_dayqfq\s*=\s*", "", result.stdout)
            data = _json.loads(text)
            code_key = list(data.get("data", {}).keys())[0]
            inner = data["data"][code_key]
            # 优先用前复权日线
            klines = inner.get("qfqday") or inner.get("day", [])
            if not klines:
                return None

            rows = []
            for row in klines:
                if len(row) < 6:
                    continue
                o, c, h, l, v = (
                    float(row[1]), float(row[2]),
                    float(row[3]), float(row[4]), float(row[5])
                )
                # 腾讯的 volume 单位是手 (100 股)
                vol_shares = v * 100
                # 用典型价估算成交额
                typical_price = (h + l + c) / 3.0
                amount = typical_price * vol_shares
                rows.append({
                    "date": row[0],
                    "open": o,
                    "close": c,
                    "high": h,
                    "low": l,
                    "volume": vol_shares,
                    "amount": amount,
                })
            if rows:
                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception:
            pass
        return None

    def get_stock_daily_data(self, stock_code, start_date, end_date):
        """
        获取股票日线数据 (含成交额, 用于 VWAP 计算)。

        数据源优先级:
        1. 新浪 (稳定，支持 1991-至今完整历史数据)
        2. 东财 (精确成交额，但可能被限流)
        3. 腾讯 (备用，成交额为估算值，但历史数据有限)

        Parameters:
        -----------
        stock_code : str
            股票代码（不带市场标识）
        start_date : str
            开始日期 YYYY-MM-DD
        end_date : str
            结束日期 YYYY-MM-DD

        Returns:
        --------
        DataFrame : 日线数据, 包含 date/open/high/low/close/volume/amount
        """
        cache_file = os.path.join(
            self.cache_dir, f"{stock_code}_{start_date}_{end_date}.csv"
        )

        if self.use_cache and os.path.exists(cache_file):
            return pd.read_csv(cache_file, parse_dates=["date"])

        # 对于 ETF，优先使用 ETF 专用接口
        if is_etf_code(stock_code):
            # ETF 优先: ETF专用接口 → 东财 → 新浪 → 腾讯
            df = self._fetch_kline_etf(stock_code, start_date, end_date)

            if df is None or len(df) == 0:
                df = self._fetch_kline_eastmoney(stock_code, start_date, end_date)

            if df is None or len(df) == 0:
                df = self._fetch_kline_sina(stock_code, start_date, end_date)

            if df is None or len(df) == 0:
                df = self._fetch_kline_tencent(stock_code, start_date, end_date)
        else:
            # A 股: 新浪 → 东财 → 腾讯
            # 1. 优先新浪 (完整历史数据，1991-至今)
            df = self._fetch_kline_sina(stock_code, start_date, end_date)

            # 2. 回退东财 (可能被限流)
            if df is None or len(df) == 0:
                df = self._fetch_kline_eastmoney(stock_code, start_date, end_date)

            # 3. 最后尝试腾讯 (成交额为估算值)
            if df is None or len(df) == 0:
                df = self._fetch_kline_tencent(stock_code, start_date, end_date)

        if df is None or len(df) == 0:
            return pd.DataFrame()

        # 保存缓存
        df.to_csv(cache_file, index=False, encoding="utf-8-sig")

        # 避免请求过快
        time.sleep(0.3)

        return df
    
    def _get_stock_name_from_cache(self, stock_code):
        """
        从缓存文件快速获取股票名称（避免完整加载股票列表）
        
        Parameters:
        -----------
        stock_code : str
            股票代码
            
        Returns:
        --------
        str : 股票名称，失败返回空字符串
        """
        try:
            cache_file = os.path.join(self.cache_dir, "stock_list.csv")
            if os.path.exists(cache_file):
                # 只读取需要的两列，加快速度
                df = pd.read_csv(cache_file, dtype={"code": str}, usecols=["code", "name"])
                df["code"] = df["code"].str.zfill(6)
                match = df[df['code'] == stock_code.zfill(6)]
                if not match.empty:
                    return match.iloc[0]['name']
        except Exception:
            pass
        return ""
    
    def _get_stock_name_from_akshare(self, stock_code):
        """
        使用akshare获取股票/ETF名称（最后的fallback）
        
        Parameters:
        -----------
        stock_code : str
            股票代码
            
        Returns:
        --------
        str : 股票名称，失败返回空字符串
        """
        try:
            import akshare as ak
            if is_etf_code(stock_code):
                # ETF: 通过东财 API 直接获取名称
                name = self._get_etf_name(stock_code)
                if name:
                    self._update_stock_cache(stock_code, name)
                    return name
            else:
                # A 股: 使用 akshare 个股信息
                df = ak.stock_individual_info_em(symbol=stock_code)
                if df is not None and not df.empty:
                    name_row = df[df['item'] == '股票简称']
                    if not name_row.empty:
                        name = name_row.iloc[0]['value']
                        self._update_stock_cache(stock_code, name)
                        return str(name)
        except Exception as e:
            pass
        return ""

    def _get_etf_name(self, stock_code):
        """
        通过东财 API 获取 ETF 名称

        Parameters:
        -----------
        stock_code : str
            ETF 代码

        Returns:
        --------
        str : ETF 名称，失败返回空字符串
        """
        try:
            market_code = _get_market_code(stock_code)
            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/get"
                f"?fltt=2&invt=2"
                f"&fields=f57,f58"
                f"&secid={market_code}.{stock_code}"
            )
            cookies = f"qgqp_b_id={uuid.uuid4().hex}"
            cmd = [
                "/usr/bin/curl", "-4", "-s", "-S",
                "--max-time", "10", "--compressed",
                "-H", f"User-Agent: {_BROWSER_UA}",
                "-b", cookies,
                url,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                data = _json.loads(result.stdout).get("data", {})
                if data:
                    return data.get("f58", "")
        except Exception:
            pass
        return ""
    
    def _update_stock_cache(self, stock_code, stock_name):
        """更新股票列表缓存"""
        try:
            cache_file = os.path.join(self.cache_dir, "stock_list.csv")
            code = stock_code.zfill(6)
            market = _get_market_label(code)
            
            # 追加到缓存文件
            with open(cache_file, 'a', encoding='utf-8-sig') as f:
                f.write(f"\n{code},{stock_name},{market}")
            print(f"  已更新缓存: {code} -> {stock_name}")
        except Exception as e:
            print(f"  更新缓存失败: {e}")

    def get_stock_fundamental(self, stock_code):
        """
        获取单只股票基本面数据（PE、市值等）
        优先使用东财 API，失败时仍返回股票名称（从新浪获取）
        
        Parameters:
        -----------
        stock_code : str
            股票代码
            
        Returns:
        --------
        dict : 基本面数据
        """
        try:
            market_code = _get_market_code(stock_code)
            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/get"
                f"?fltt=2&invt=2"
                f"&fields=f57,f58,f43,f162,f116,f167"
                f"&secid={market_code}.{stock_code}"
            )
            # f57=代码 f58=名称 f43=最新价 f162=PE(动) f116=总市值 f167=市净率
            cookies = (
                f"qgqp_b_id={uuid.uuid4().hex}; nid18={uuid.uuid4().hex}"
            )
            cmd = [
                "/usr/bin/curl", "-4", "-s", "-S",
                "--max-time", "10", "--compressed",
                "-H", f"User-Agent: {_BROWSER_UA}",
                "-b", cookies,
                url,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0 or not result.stdout.strip():
                raise RuntimeError("curl 请求失败")

            data = _json.loads(result.stdout).get("data", {})
            
            if not data:
                raise RuntimeError("返回数据为空")

            return {
                "stock_code": data.get("f57", stock_code),
                "stock_name": data.get("f58", ""),
                "pe_ttm": data.get("f162"),
                "market_cap": data.get("f116", 0),
                "latest_price": data.get("f43"),
            }
        except Exception as e:
            # 东财失败时，尝试从缓存获取股票名称
            name = self._get_stock_name_from_cache(stock_code)
            if not name:
                # 缓存也没有，尝试用akshare获取
                name = self._get_stock_name_from_akshare(stock_code)
            
            if name:
                return {
                    "stock_code": stock_code,
                    "stock_name": name,
                    "pe_ttm": None,
                    "market_cap": None,
                    "latest_price": None,
                }
            # print(f"获取 {stock_code} 基本面数据失败: {e}")
            return None
    
    # -------- 全市场行情 (批量 ulist.np/get，不走分页 clist) --------

    def _fetch_ttm_dividend_data(self):
        """
        从东财 datacenter-web 获取最近 12 个月的全市场分红明细。

        API: RPT_SHAREBONUS_DET
        字段: SECURITY_CODE, PRETAX_BONUS_RMB (每 10 股税前派现), EX_DIVIDEND_DATE
        按 EX_DIVIDEND_DATE 倒序分页获取，API 每页最多 500 条。

        Returns:
            dict: {stock_code: ttm_dividend_per_share}
        """
        from collections import defaultdict
        from datetime import timedelta

        cookies = f"qgqp_b_id={uuid.uuid4().hex}; nid18={uuid.uuid4().hex}"

        # 12 个月前的日期作为起点
        cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        all_records = []
        for page in range(1, 30):  # 最多 30 页 (15000 条)
            url = (
                "https://datacenter-web.eastmoney.com/api/data/v1/get"
                "?sortColumns=EX_DIVIDEND_DATE&sortTypes=-1"
                f"&pageSize=500&pageNumber={page}"
                "&reportName=RPT_SHAREBONUS_DET"
                "&columns=SECURITY_CODE,PRETAX_BONUS_RMB,EX_DIVIDEND_DATE"
            )
            cmd = [
                "/usr/bin/curl", "-4", "-s", "-S", "--max-time", "15",
                "--compressed", "-G",
                "-H", f"User-Agent: {_BROWSER_UA}",
                "-b", cookies,
                "--data-urlencode", f"filter=(EX_DIVIDEND_DATE>='{cutoff}')",
                url,
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=20
                )
                if result.returncode != 0 or not result.stdout.strip():
                    break
                data = _json.loads(result.stdout)
                records = data.get("result", {}).get("data", [])
                if not records:
                    break
                all_records.extend(records)
                if len(records) < 500:
                    break  # 最后一页
            except Exception as e:
                print(f"  获取分红数据第 {page} 页失败: {e}")
                break

            time.sleep(0.3)

        # 按股票代码汇总 TTM 分红 (PRETAX_BONUS_RMB = 每 10 股)
        totals = defaultdict(float)
        for r in all_records:
            code = r.get("SECURITY_CODE", "")
            bonus = r.get("PRETAX_BONUS_RMB") or 0
            totals[code] += bonus

        # 转为每股
        return {code: total / 10.0 for code, total in totals.items()}

    def _fetch_batch_fundamentals(self, stock_codes, batch_size=500):
        """
        批量获取基本面数据:
        1. ulist.np/get: PE(f9), 总市值(f20), 最新价(f2)
        2. datacenter-web RPT_SHAREBONUS_DET: TTM 分红 → 计算股息率

        f127 在 ulist.np 中不是可靠的股息率字段（很多股票返回错误值），
        因此改为用实际分红数据自行计算 TTM 股息率。

        Returns:
            pd.DataFrame
        """
        cookies = (
            f"qgqp_b_id={uuid.uuid4().hex}; nid18={uuid.uuid4().hex}"
        )

        # ---------- Step 1: ulist.np 获取 PE / 市值 / 最新价 ----------
        secid_map = {}
        for code in stock_codes:
            code = str(code).zfill(6)
            market = _get_market_code(code)
            secid_map[code] = f"{market}.{code}"

        all_items = []
        codes_list = list(secid_map.values())
        total_batches = math.ceil(len(codes_list) / batch_size)

        for i in range(0, len(codes_list), batch_size):
            batch = codes_list[i:i + batch_size]
            batch_num = i // batch_size + 1
            secids_str = ",".join(batch)

            url = (
                f"https://push2his.eastmoney.com/api/qt/ulist.np/get"
                f"?fltt=2&invt=2"
                f"&fields=f12,f14,f2,f9,f20"
                f"&secids={secids_str}"
            )
            # f12=代码 f14=名称 f2=最新价 f9=PE(动) f20=总市值

            cmd = [
                "/usr/bin/curl", "-4", "-s", "-S",
                "--max-time", "30", "--compressed",
                "-H", f"User-Agent: {_BROWSER_UA}",
                "-H", "Accept: */*",
                "-H", 'sec-ch-ua-platform: "macOS"',
                "-b", cookies,
                url,
            ]

            # 重试逻辑
            last_err = None
            for attempt in range(3):
                if attempt > 0:
                    delay = 2 ** attempt + 1
                    time.sleep(delay)

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=40
                )
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        data = _json.loads(result.stdout)
                        diff = data.get("data", {}).get("diff", [])
                        if isinstance(diff, dict):
                            all_items.extend(diff.values())
                        else:
                            all_items.extend(diff)
                        last_err = None
                        break
                    except _json.JSONDecodeError as e:
                        last_err = e
                        continue
                last_err = _requests.ConnectionError(
                    f"batch {batch_num}/{total_batches} 失败"
                )

            if last_err:
                print(f"  警告: 第 {batch_num}/{total_batches} 批失败: {last_err}")

            # 批次间防频率限制
            if i + batch_size < len(codes_list):
                time.sleep(0.5)

        if not all_items:
            raise RuntimeError("所有批次均失败")

        df = pd.DataFrame(all_items)
        df = df.rename(columns={
            "f12": "stock_code",
            "f14": "stock_name",
            "f2": "latest_price",
            "f9": "pe_ttm",
            "f20": "market_cap",
        })
        df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
        
        # 确保 stock_name 列存在，即使 API 未返回 f14
        if "stock_name" not in df.columns:
            df["stock_name"] = ""
        else:
            # 将 NaN 和空值统一处理为空字符串
            df["stock_name"] = df["stock_name"].fillna("").astype(str).str.strip()
        
        # 对于名称为空的股票，尝试从缓存获取名称
        empty_name_mask = (df["stock_name"] == "") | (df["stock_name"] == df["stock_code"])
        if empty_name_mask.any():
            print(f"  发现 {empty_name_mask.sum()} 只股票名称缺失，尝试从缓存补全...")
            cache_file = os.path.join(self.cache_dir, "stock_list.csv")
            if os.path.exists(cache_file):
                try:
                    name_df = pd.read_csv(cache_file, dtype={"code": str}, usecols=["code", "name"])
                    name_df["code"] = name_df["code"].str.zfill(6)
                    name_map = dict(zip(name_df["code"], name_df["name"]))
                    
                    def fill_name(row):
                        if row["stock_name"] == "" or row["stock_name"] == row["stock_code"]:
                            return name_map.get(row["stock_code"], row["stock_code"])
                        return row["stock_name"]
                    
                    df["stock_name"] = df.apply(fill_name, axis=1)
                    filled = empty_name_mask.sum() - ((df["stock_name"] == "") | (df["stock_name"] == df["stock_code"])).sum()
                    if filled > 0:
                        print(f"  成功补全 {filled} 只股票名称")
                except Exception as e:
                    print(f"  从缓存补全名称失败: {e}")
        
        for col in ("pe_ttm", "market_cap", "latest_price"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # ---------- Step 2: 从分红数据计算 TTM 股息率 ----------
        print("  获取分红数据计算 TTM 股息率...")
        ttm_dividends = self._fetch_ttm_dividend_data()
        df["ttm_dividend_per_share"] = df["stock_code"].map(ttm_dividends).fillna(0)
        df["dividend_yield"] = df.apply(
            lambda row: (
                round(row["ttm_dividend_per_share"] / row["latest_price"] * 100, 2)
                if pd.notna(row["latest_price"]) and row["latest_price"] > 0
                else 0
            ),
            axis=1,
        )

        return df

    def batch_get_fundamentals(self, stock_codes):
        """
        批量获取基本面数据 (直接调用东财 API，不走 akshare 分页)
        
        Parameters:
        -----------
        stock_codes : list
            股票代码列表
            
        Returns:
        --------
        DataFrame : 基本面数据
        """
        cache_file = os.path.join(self.cache_dir, "fundamentals_latest.csv")
        
        # 统一股票代码格式
        normalized_codes = []
        for code in stock_codes:
            s = str(code)
            digits = "".join([c for c in s if c.isdigit()])
            if len(digits) >= 6:
                normalized_codes.append(digits[-6:])
            else:
                normalized_codes.append(s.zfill(6))
        stock_codes = normalized_codes
        
        if not stock_codes:
            return pd.DataFrame()
        
        # 检查缓存
        if self.use_cache and os.path.exists(cache_file):
            mod_time = os.path.getmtime(cache_file)
            mod_date = datetime.fromtimestamp(mod_time).date()
            if mod_date == datetime.now().date():
                print("使用缓存的基本面数据")
                df = pd.read_csv(cache_file, dtype={"stock_code": str})
                if "stock_code" in df.columns:
                    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
                filtered = df[df['stock_code'].isin(stock_codes)]
                if len(filtered) > 0:
                    return filtered
        
        print("获取全市场基本面数据 (批量 ulist API)...")
        try:
            df = self._fetch_batch_fundamentals(stock_codes)
            
            # 保存缓存
            df.to_csv(cache_file, index=False, encoding='utf-8-sig')
            print(f"获取到 {len(df)} 只股票的基本面数据")
            
            # 过滤指定股票
            filtered = df[df['stock_code'].isin(stock_codes)]
            return filtered
            
        except Exception as e:
            print(f"获取基本面数据失败: {e}")
            
            # 使用旧的缓存数据
            if os.path.exists(cache_file):
                print("使用旧的缓存数据")
                df = pd.read_csv(cache_file, dtype={"stock_code": str})
                if "stock_code" in df.columns:
                    df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)
                return df[df['stock_code'].isin(stock_codes)]
            
            return pd.DataFrame()
    
    def get_index_components(self, index_code='000300'):
        """
        获取指数成分股
        
        Parameters:
        -----------
        index_code : str
            指数代码，如 '000300'(沪深300)
            
        Returns:
        --------
        list : 成分股代码列表
        """
        try:
            # 使用 akshare 获取指数成分股（通过 curl）
            if index_code == '000300':
                with self._use_curl():
                    df = ak.index_stock_cons_csindex(symbol="000300")
                return df['成分券代码'].tolist()
            return []
        except Exception as e:
            print(f"获取指数成分股失败: {e}")
            return []
