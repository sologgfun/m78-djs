"""
股票服务模块
"""
import sys
import os
import math
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pywencai
from data_fetcher import DataFetcher, is_etf_code


class StockService:
    """股票服务类"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self._stock_list_cache = None
        self._fundamentals_cache = None

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(val):
        """安全转 float，无法转换或 NaN 返回 None"""
        if val is None:
            return None
        try:
            f = float(val)
            if math.isnan(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_df(res):
        """
        从 pywencai 返回值中提取 DataFrame。
        pywencai 有时返回 DataFrame，有时返回 dict(tableV1=DataFrame)。
        """
        if isinstance(res, pd.DataFrame):
            return res
        if isinstance(res, dict):
            for v in res.values():
                if isinstance(v, pd.DataFrame) and len(v) > 0:
                    return v
        return None

    @staticmethod
    def _find_code_col(df):
        """在 DataFrame 列中找到代码列（兼容 '股票代码'、'代码'、'code'）"""
        for col in df.columns:
            cl = str(col).lower()
            if col == 'code' or cl == '股票代码' or cl == '代码':
                return col
            if '股票代码' in cl:
                return col
        # 最后尝试只含 '代码' 的
        for col in df.columns:
            if '代码' in str(col):
                return col
        return None

    @staticmethod
    def _find_name_col(df):
        """在 DataFrame 列中找到名称列（兼容 '股票简称'、'名称'、'name'）"""
        for col in df.columns:
            cl = str(col).lower()
            if col == 'name' or cl == '股票简称' or cl == '名称':
                return col
            if '股票简称' in cl:
                return col
        for col in df.columns:
            if '简称' in str(col) or '名称' in str(col):
                return col
        return None

    @staticmethod
    def _classify_columns(df):
        """
        将 DataFrame 的所有列按指标分类。
        返回 dict: {
            'code': str|None, 'name': str|None,
            'pe': list[str], 'dividend': list[str],
            'ratio': list[str], 'price': list[str], 'vwap': list[str]
        }
        """
        result = {
            'code': None, 'name': None,
            'pe': [], 'dividend': [], 'ratio': [],
            'price': [], 'vwap': [],
        }
        for col in df.columns:
            cl = str(col).lower()

            # --- 代码 & 名称 ---
            if result['code'] is None and (
                col == 'code' or cl in ('股票代码', '代码') or '股票代码' in cl
            ):
                result['code'] = col
                continue
            if result['code'] is None and '代码' in cl:
                result['code'] = col
                continue
            if result['name'] is None and (
                col == 'name' or cl in ('股票简称', '名称') or '股票简称' in cl
            ):
                result['name'] = col
                continue
            if result['name'] is None and ('简称' in cl or '名称' in cl):
                result['name'] = col
                continue

            # --- PE ---
            if '市盈率' in cl and '预测' not in cl:
                result['pe'].append(col)
                continue

            # --- 股息率 ---
            if '股息率' in cl or '股票获利率' in cl:
                result['dividend'].append(col)
                continue

            # --- ratio: 收盘价/均价 ---
            # pywencai 返回格式多变:
            #   {(}收盘价:不复权[…]{/}…{)}
            #   (收盘价:不复权[…]/区间成交均价[…])
            #   收盘价/120日均线
            if col.startswith('{(}') or col.startswith('('):
                # 带括号的复合指标 → ratio
                result['ratio'].append(col)
                continue
            if '收盘价' in cl and ('均价' in cl or '均线' in cl):
                result['ratio'].append(col)
                continue

            # --- 单独的收盘价 ---
            if '收盘价' in cl and '区间' not in cl and '均价' not in cl and '均线' not in cl:
                result['price'].append(col)
                continue

            # --- 单独的区间成交均价 (VWAP / MA120 近似) ---
            if '区间成交均价' in cl and '收盘价' not in cl:
                result['vwap'].append(col)
                continue

        return result

    def _first_valid(self, row, cols):
        """从多个候选列中取出第一个非空 float"""
        for c in cols:
            v = self._safe_float(row.get(c, None))
            if v is not None:
                return v
        return None

    @staticmethod
    def _extract_code(raw):
        """从原始代码字符串提取6位代码"""
        s = str(raw).strip()
        if '.' in s:
            s = s.split('.')[0]
        return s if s else ''

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_all_stocks(self):
        """获取所有股票列表"""
        if self._stock_list_cache is None:
            df = self.data_fetcher.get_stock_list()
            if df is not None and len(df) > 0:
                self._stock_list_cache = df[['code', 'name']].to_dict('records')
            else:
                self._stock_list_cache = []
        return self._stock_list_cache
    
    def search_stocks(self, keyword):
        """
        搜索股票：
        1. 用东财建议 API 快速搜索（支持名称/代码/拼音）
        2. 用 pywencai 补充 PE、股息率、MA120 偏离度等指标
        """
        if not keyword:
            return self.get_all_stocks()[:50]

        kw = keyword.strip()
        
        print(f"搜索股票: {kw}")
        base_results = self._search_eastmoney_suggest(kw)
        
        if not base_results:
            print("东财建议无结果")
            return []
        
        print(f"东财建议返回 {len(base_results)} 条结果")
        
        top_results = base_results[:20]
        enriched = self._enrich_stocks_with_pywencai(top_results)
        
        return enriched
    
    def _enrich_stocks_with_pywencai(self, stock_list):
        """
        用 pywencai 补充股票详情: PE, 股息率, 收盘价/120MA
        对于 ETF/LOF，PE 和股息率不适用，仅尝试获取价格/MA120 比值。
        """
        if not stock_list:
            return []
        
        # 将 A 股和 ETF 分开处理
        stock_codes = [s['code'] for s in stock_list if not is_etf_code(s['code'])]
        etf_codes = [s['code'] for s in stock_list if is_etf_code(s['code'])]
        
        # 为 A 股查询 pywencai
        codes = [s['code'] for s in stock_list]
        codes_str = ",".join(stock_codes) if stock_codes else ""
        
        try:
            if stock_codes:
                query = (
                    f"股票代码在({codes_str})中，"
                    f"市盈率(pe)，股息率(股票获利率)，"
                    f"(收盘价/120天的区间成交均价）"
                )
                print(f"[搜索补充] 批量查询: {query}")
            else:
                query = None
            
            df = None
            if query:
                res = pywencai.get(question=query, query_type='stock', loop=True)
                df = self._extract_df(res)
            
            # ---------- 批量结果解析 ----------
            detail_map = {}  # code -> {pe, dividend, ratio}
            if df is not None and len(df) > 0:
                print(f"[搜索补充] 批量返回 {len(df)} 行, 列: {list(df.columns)}")
                cols = self._classify_columns(df)
                code_col = cols['code']
                print(f"[搜索补充] 分类: code={code_col}, pe={cols['pe']}, div={cols['dividend']}, ratio={cols['ratio']}")
                
                if code_col:
                    for _, row in df.iterrows():
                        code = self._extract_code(row.get(code_col, ''))
                        if not code:
                            continue
                        pe = self._first_valid(row, cols['pe'])
                        dividend = self._first_valid(row, cols['dividend'])
                        ratio = self._first_valid(row, cols['ratio'])
                        
                        if code in detail_map:
                            d = detail_map[code]
                            if d['pe'] is None and pe is not None:
                                d['pe'] = pe
                            if d['dividend'] is None and dividend is not None:
                                d['dividend'] = dividend
                            if d['ratio'] is None and ratio is not None:
                                d['ratio'] = ratio
                        else:
                            detail_map[code] = {'pe': pe, 'dividend': dividend, 'ratio': ratio}
            
            # ---------- 对缺失数据的 A 股逐个补查 ----------
            # pywencai 多股票查询时经常不返回股息率列，需要逐个补全
            # 注意: ETF 不需要补查 PE/股息率（它们本身就没有）
            codes_need_fill = [
                c for c in stock_codes
                if c not in detail_map
                or detail_map[c].get('dividend') is None
                or detail_map[c].get('ratio') is None
            ]
            if codes_need_fill:
                print(f"[搜索补充] {len(codes_need_fill)} 只股票数据不全，逐个补查...")
                for code in codes_need_fill:
                    try:
                        q2 = f"{code}的市盈率(pe)，股息率，收盘价/120日均线"
                        res2 = pywencai.get(question=q2, query_type='stock', loop=True)
                        df2 = self._extract_df(res2)
                        if df2 is None or len(df2) == 0:
                            continue
                        cols2 = self._classify_columns(df2)
                        # 合并所有行
                        pe2 = None; div2 = None; ratio2 = None
                        for _, row2 in df2.iterrows():
                            if pe2 is None:
                                pe2 = self._first_valid(row2, cols2['pe'])
                            if div2 is None:
                                div2 = self._first_valid(row2, cols2['dividend'])
                            if ratio2 is None:
                                ratio2 = self._first_valid(row2, cols2['ratio'])
                        
                        if code not in detail_map:
                            detail_map[code] = {'pe': pe2, 'dividend': div2, 'ratio': ratio2}
                        else:
                            d = detail_map[code]
                            if d['pe'] is None and pe2 is not None:
                                d['pe'] = pe2
                            if d['dividend'] is None and div2 is not None:
                                d['dividend'] = div2
                            if d['ratio'] is None and ratio2 is not None:
                                d['ratio'] = ratio2
                        print(f"[搜索补充] 补查 {code}: pe={detail_map[code]['pe']}, div={detail_map[code]['dividend']}, ratio={detail_map[code]['ratio']}")
                    except Exception as ex:
                        print(f"[搜索补充] 补查 {code} 失败: {ex}")
            
            # ---------- 为 ETF 补充价格/MA120 ----------
            # ETF 没有 PE 和股息率，但价格/MA120 比值仍然需要
            if etf_codes:
                print(f"[搜索补充] 为 {len(etf_codes)} 只 ETF 计算价格/MA120...")
                for code in etf_codes:
                    ratio_val = self._calc_etf_price_ratio(code)
                    detail_map[code] = {'pe': None, 'dividend': None, 'ratio': ratio_val}
                    if ratio_val is not None:
                        print(f"[搜索补充] ETF {code}: 价/MA120={ratio_val:.4f}")
                    else:
                        print(f"[搜索补充] ETF {code}: 无法计算价/MA120")
            
            # ---------- 合并结果 ----------
            enriched = []
            for stock in stock_list:
                code = stock['code']
                d = detail_map.get(code, {})
                pe_val = d.get('pe')
                div_val = d.get('dividend')
                ratio_val = d.get('ratio')
                enriched.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'pe': round(pe_val, 2) if pe_val is not None else None,
                    'dividend': round(div_val, 2) if div_val is not None else None,
                    'ratio': round(ratio_val, 4) if ratio_val is not None else None,
                })
            
            return enriched
            
        except Exception as e:
            print(f"[搜索补充] pywencai 失败: {e}")
            import traceback
            traceback.print_exc()
            return stock_list

    @staticmethod
    def _search_eastmoney_suggest(keyword):
        """调用东财搜索建议 API，支持名称/拼音/代码。支持 A 股 + ETF/LOF。"""
        import subprocess, json
        from urllib.parse import quote

        url = (
            f"https://searchapi.eastmoney.com/api/suggest/get"
            f"?input={quote(keyword)}&type=14"
            f"&token=D43BF722C8E33BDC906FB84D85E326E8&count=30"
        )
        try:
            result = subprocess.run(
                ["/usr/bin/curl", "-4", "-s", "--max-time", "3", url],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            data = json.loads(result.stdout)
            items = data.get("QuotationCodeTable", {}).get("Data", [])
            results = []
            for item in items:
                classify = item.get("Classify", "")
                code = str(item.get("Code", "")).zfill(6)
                name = item.get("Name", "")
                if not code or not name:
                    continue
                # A 股直接接受
                if classify == "AStock":
                    results.append({"code": code, "name": name})
                # 基金中仅接受场内 ETF/LOF（排除场外基金）
                elif classify == "Fund" and is_etf_code(code):
                    results.append({"code": code, "name": name})
            return results
        except Exception:
            return []
    
    def _calc_etf_price_ratio(self, code):
        """
        计算 ETF 的 当前价格 / MA120 比值。
        从东财获取最近约 200 个交易日的数据来计算 120 日均线。

        Returns: float (如 0.9523) 或 None
        """
        from datetime import timedelta
        try:
            end_dt = datetime.now()
            # 300 个自然日 ≈ 200+ 个交易日，确保覆盖 120 日均线所需数据
            start_dt = end_dt - timedelta(days=300)
            s_date = start_dt.strftime('%Y-%m-%d')
            e_date = end_dt.strftime('%Y-%m-%d')

            df = self.data_fetcher.get_stock_daily_data(code, s_date, e_date)
            if df is None or len(df) < 120:
                return None

            ma120 = df['close'].rolling(window=120).mean().iloc[-1]
            current_price = df['close'].iloc[-1]

            if pd.notna(ma120) and ma120 > 0:
                return round(current_price / ma120, 4)
        except Exception as e:
            print(f"[ETF ratio] 计算 {code} 失败: {e}")
        return None

    def screen_etfs(self, keyword=''):
        """
        按领域关键词筛选场内 ETF / LOF。

        筛选策略（三路并行，结果去重合并）：
        1. 东财搜索建议 API（快速、精确匹配名称/拼音）
        2. ETF 实时列表 + 名称关键词过滤（完整覆盖）
        3. pywencai 语义搜索（兜底补充）

        Parameters:
        -----------
        keyword : str
            领域关键词，如 '半导体'、'沪深300'、'医药'、'黄金'

        Returns:
        --------
        list[dict] : [{'code': '510300', 'name': '沪深300ETF'}, ...]
        """
        results = []
        seen = set()

        # ---------- 方法 1: 东财搜索建议 API（最快）----------
        if keyword:
            try:
                suggest = self._search_eastmoney_suggest(keyword)
                etf_suggest = [s for s in suggest if is_etf_code(s['code'])]
                for s in etf_suggest:
                    if s['code'] not in seen:
                        seen.add(s['code'])
                        results.append(s)
                if etf_suggest:
                    print(f"[ETF筛选] 东财建议匹配 {len(etf_suggest)} 只")
            except Exception as e:
                print(f"[ETF筛选] 东财建议失败: {e}")

        # ---------- 方法 2: akshare ETF 实时列表 + 名称过滤（最全）----------
        try:
            etf_df = self.data_fetcher._fetch_etf_list()
            if etf_df is not None and len(etf_df) > 0:
                if keyword:
                    etf_df = etf_df[etf_df['name'].str.contains(keyword, case=False, na=False)]
                for _, row in etf_df.iterrows():
                    code = str(row['code']).zfill(6)
                    if code not in seen:
                        seen.add(code)
                        results.append({'code': code, 'name': row.get('name', '')})
                print(f"[ETF筛选] ETF列表匹配 {len(results) - len([r for r in results if r['code'] in seen]) + len(results)} -> 累计 {len(results)} 只")
        except Exception as e:
            print(f"[ETF筛选] ETF列表获取失败: {e}")

        # ---------- 方法 3: pywencai 语义搜索（补充）----------
        if keyword and len(results) < 5:
            try:
                # 用 stock 类型查询，部分 ETF 也会出现在股票查询中
                query = f"{keyword}ETF"
                print(f"[ETF筛选] pywencai 补充: {query}")
                res = pywencai.get(question=query, query_type='stock', loop=True)
                df = self._extract_df(res)
                if df is not None and len(df) > 0:
                    code_col = self._find_code_col(df)
                    name_col = self._find_name_col(df)
                    if code_col:
                        for _, row in df.iterrows():
                            code = self._extract_code(row.get(code_col, ''))
                            if code and is_etf_code(code) and code not in seen:
                                seen.add(code)
                                name = str(row.get(name_col, '')) if name_col else ''
                                results.append({'code': code, 'name': name})
            except Exception as e:
                print(f"[ETF筛选] pywencai 补充失败: {e}")

        print(f"[ETF筛选] 关键词='{keyword}'，共找到 {len(results)} 只 ETF")
        return results

    def screen_stocks(self, pe_max=20, dividend_min=3, market_cap_min=0):
        """
        按 PE(TTM)、股息率筛选股票。
        返回 list[dict]，每项含 code 和 name。
        """
        try:
            print(f"筛选股票: PE < {pe_max}, 股息率 > {dividend_min}%")
            
            query = (
                f"市盈率(ttm)<{pe_max}，"
                f"市盈率(ttm)>0，"
                f"股息率(近12个月)>{dividend_min}，"
                f"非ST，非停牌"
            )
            if market_cap_min > 0:
                query += f"，总市值>{market_cap_min}亿"
                
            res = pywencai.get(question=query, query_type='stock', loop=True)
            df = self._extract_df(res)
            
            if df is None or len(df) == 0:
                print("未找到符合条件的股票")
                return []
            
            code_col = self._find_code_col(df)
            name_col = self._find_name_col(df)
            
            if code_col is None:
                print(f"无法找到股票代码列, 列名: {list(df.columns)}")
                return []
            
            results = []
            seen = set()
            for _, row in df.iterrows():
                code = self._extract_code(row.get(code_col, ''))
                if not code or code in seen:
                    continue
                seen.add(code)
                name = str(row.get(name_col, '')) if name_col else ''
                results.append({'code': code, 'name': name})
            
            print(f"筛选完成，找到 {len(results)} 只股票")
            return results
            
        except Exception as e:
            print(f"筛选股票出错: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_djs_recommendations(self, pe_max=20, dividend_min=3, price_ratio=90):
        """
        获取符合"点金术"逻辑的股票推荐。
        直接调用同花顺 i问财 (pywencai) 自然语言选股。
        """
        try:
            query = (
                f"市盈率(pe)>0倍且市盈率(pe)<{pe_max}倍，"
                f"股息率(股票获利率)>={dividend_min}%，"
                f"(收盘价/120天的区间成交均价）<{price_ratio}%"
            )
            print(f"DJS 筛选: 调用 i问财 -> {query}")

            res = pywencai.get(question=query, query_type='stock', loop=True)
            df = self._extract_df(res)

            if df is None or len(df) == 0:
                print("i问财 返回空结果")
                return []

            print(f"i问财 返回 {len(df)} 行")

            cols = self._classify_columns(df)
            code_col = cols['code']
            name_col = cols['name']

            if not code_col:
                print(f"DJS: 无法识别代码列, 列名: {list(df.columns)}")
                return []

            # 按 code 合并多行
            merged = {}
            for _, row in df.iterrows():
                code = self._extract_code(row.get(code_col, ''))
                if not code:
                    continue

                name = str(row.get(name_col, '')) if name_col else ''
                pe = self._first_valid(row, cols['pe'])
                dividend = self._first_valid(row, cols['dividend'])
                price = self._first_valid(row, cols['price'])
                vwap = self._first_valid(row, cols['vwap'])
                ratio = self._first_valid(row, cols['ratio'])

                if code in merged:
                    m = merged[code]
                    if not m['name'] and name:
                        m['name'] = name
                    if m['pe'] is None and pe is not None:
                        m['pe'] = pe
                    if m['dividend'] is None and dividend is not None:
                        m['dividend'] = dividend
                    if m['price'] is None and price is not None:
                        m['price'] = price
                    if m['vwap'] is None and vwap is not None:
                        m['vwap'] = vwap
                    if m['ratio'] is None and ratio is not None:
                        m['ratio'] = ratio
                else:
                    merged[code] = {
                        'name': name, 'pe': pe, 'dividend': dividend,
                        'price': price, 'vwap': vwap, 'ratio': ratio,
                    }

            results = []
            for code, m in merged.items():
                results.append({
                    'code': code,
                    'name': m['name'] or '',
                    'pe': round(m['pe'], 2) if m['pe'] is not None else None,
                    'dividend': round(m['dividend'], 2) if m['dividend'] is not None else None,
                    'price': round(m['price'], 2) if m['price'] is not None else None,
                    'ma120': round(m['vwap'], 2) if m['vwap'] is not None else None,
                    'ratio': round(m['ratio'], 4) if m['ratio'] is not None else None,
                })

            results.sort(key=lambda x: x['ratio'] if x['ratio'] else 1)

            print(f"DJS 筛选完成，返回 {len(results)} 只推荐股票")
            return results

        except Exception as e:
            print(f"DJS 筛选失败: {e}")
            import traceback
            traceback.print_exc()
            return []
