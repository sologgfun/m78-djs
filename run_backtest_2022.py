#!/usr/bin/env python3
"""
2022 年全市场回测脚本
多线程并行加载数据，大幅提速
"""
import sys, os, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
from indicators import add_all_indicators
from strategy import LadderStrategy
from portfolio import Portfolio
from config import *

# ========== 配置 ==========
START_DATE = "2022-01-01"
END_DATE = "2022-12-31"
INITIAL_CAPITAL = 200000
MAX_POSITIONS = 5
PARALLEL_WORKERS = 10  # 并行加载线程数

# 策略参数（和前端默认一致）
STRATEGY_CONFIG = {
    'ENTRY_SIGNAL_THRESHOLD': 0.88,
    'FIRST_POSITION_RATIO': 0.10,
    'LADDER_DOWN': [(0.88, 0.10), (0.80, 0.20), (0.70, 0.30), (0.60, 0.40)],
    'SINGLE_LAYER_PROFIT': 0.12,
    'FULL_CLEAR_THRESHOLD': 1.12,
    'USE_DYNAMIC_ATR': False,
}


def load_candidates():
    """读取候选股代码"""
    path = os.path.join(os.path.dirname(__file__), "candidates_2022.txt")
    with open(path) as f:
        return [c.strip() for c in f if c.strip()]


def fetch_one_stock(fetcher, code, start, end):
    """加载单只股票数据（供线程池调用）"""
    try:
        df = fetcher.get_stock_daily_data(code, start, end)
        if df is not None and len(df) >= 120:
            df = add_all_indicators(df)
            return code, df
    except Exception as e:
        pass
    return code, None


def run():
    codes = load_candidates()
    print(f"候选股: {len(codes)} 只")
    print(f"回测区间: {START_DATE} ~ {END_DATE}")
    print(f"并行线程: {PARALLEL_WORKERS}")
    print()

    fetcher = DataFetcher(cache_dir=DATA_CACHE_DIR, use_cache=USE_CACHE)
    strategy = LadderStrategy(STRATEGY_CONFIG)
    portfolio = Portfolio(INITIAL_CAPITAL, COMMISSION_RATE, STAMP_TAX)

    # ===== 1. 并行加载基本面 =====
    t0 = time.time()
    print(">>> 加载基本面数据...")
    fundamentals = fetcher.batch_get_fundamentals(codes)
    if fundamentals is not None:
        print(f"    基本面: {len(fundamentals)} 只 ({time.time()-t0:.1f}s)")
    else:
        print("    基本面获取失败，继续...")
        import pandas as pd
        fundamentals = pd.DataFrame({
            'stock_code': codes,
            'stock_name': codes,
            'pe_ttm': [None]*len(codes),
            'market_cap': [None]*len(codes),
            'dividend_yield': [None]*len(codes),
        })

    # ===== 2. 多线程并行加载 K 线数据 =====
    t1 = time.time()
    print(f"\n>>> 并行加载 K 线数据 ({len(codes)} 只)...")
    stock_data = {}
    done = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = {
            pool.submit(fetch_one_stock, fetcher, code, START_DATE, END_DATE): code
            for code in codes
        }
        for future in as_completed(futures):
            code, df = future.result()
            done += 1
            if df is not None:
                stock_data[code] = df
            else:
                failed += 1
            if done % 20 == 0 or done == len(codes):
                elapsed = time.time() - t1
                print(f"    [{done}/{len(codes)}] 成功={len(stock_data)} 失败={failed} ({elapsed:.0f}s)")

    print(f"    K线加载完成: {len(stock_data)}/{len(codes)} 只 ({time.time()-t1:.1f}s)")

    # ===== 3. 运行回测引擎 =====
    t2 = time.time()
    print(f"\n>>> 运行回测引擎...")

    # 使用 BacktestEngine 但跳过数据加载
    from backtest_engine import BacktestEngine
    engine = BacktestEngine(
        start_date=START_DATE,
        end_date=END_DATE,
        initial_capital=INITIAL_CAPITAL,
        max_positions=MAX_POSITIONS,
        config=STRATEGY_CONFIG
    )
    engine.stock_data = stock_data
    engine.fundamentals = fundamentals
    engine.qualified_stocks = list(stock_data.keys())

    # 加载指数数据
    engine._load_index_data()

    # 运行回测
    engine.run()
    print(f"    回测完成 ({time.time()-t2:.1f}s)")

    # ===== 4. 分析结果 =====
    t3 = time.time()
    print(f"\n>>> 分析结果...")
    results = engine.analyze_results()
    print(f"    分析完成 ({time.time()-t3:.1f}s)")

    total_time = time.time() - t0
    print(f"\n总耗时: {total_time:.1f}s")

    # ===== 5. 保存结果并生成报告 =====
    save_report(results, stock_data, total_time)

    return results


def save_report(results, stock_data, total_time):
    """生成 Markdown 报告"""
    overall = results.get('overall_stats', {})
    
    # stock_results 可能是 DataFrame 或 list
    sr = results.get('stock_results', [])
    import pandas as pd
    if isinstance(sr, pd.DataFrame):
        stock_rows = sr.to_dict('records')
    else:
        stock_rows = sr if isinstance(sr, list) else []

    trades_raw = results.get('trades', [])
    if isinstance(trades_raw, pd.DataFrame):
        all_trades = trades_raw.to_dict('records')
    else:
        all_trades = trades_raw if isinstance(trades_raw, list) else []

    # 有交易的股票
    traded = [s for s in stock_rows if s.get('交易次数', 0) > 0]
    no_trade = [s for s in stock_rows if s.get('交易次数', 0) == 0]

    # 按总收益率排序
    def parse_pct(v):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            return float(v.replace('%', '')) if v.replace('%','').replace('-','').replace('.','').isdigit() else 0
        return 0

    traded.sort(key=lambda s: parse_pct(s.get('总收益率', 0)), reverse=True)

    # 统计
    total_stocks = len(stock_data)
    traded_count = len(traded)
    profit_stocks = [s for s in traded if parse_pct(s.get('总收益率', 0)) > 0]
    loss_stocks = [s for s in traded if parse_pct(s.get('总收益率', 0)) < 0]
    zero_stocks = [s for s in traded if parse_pct(s.get('总收益率', 0)) == 0]

    lines = []
    lines.append("# 2022年全市场回测报告")
    lines.append("")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 回测耗时: {total_time:.0f} 秒")
    lines.append("")

    lines.append("## 一、策略说明")
    lines.append("")
    lines.append("本次回测使用 **白马梯级轮动策略**，核心逻辑如下：")
    lines.append("")
    lines.append("| 参数 | 值 |")
    lines.append("|------|------|")
    lines.append("| 入场信号 | 价格 ≤ MA120 × 88% |")
    lines.append("| 首次仓位 | 总资金 10% |")
    lines.append("| 梯级加仓 | 88%→10%, 80%→20%, 70%→30%, 60%→40% |")
    lines.append("| 单层止盈 | 12% |")
    lines.append("| 全仓清空 | 价格 ≥ MA120 × 112% |")
    lines.append(f"| 初始资金 | ¥{INITIAL_CAPITAL:,.0f} |")
    lines.append(f"| 最大持仓 | {MAX_POSITIONS} 只 |")
    lines.append("")

    lines.append("## 二、数据范围")
    lines.append("")
    lines.append(f"- **回测区间**: {START_DATE} ~ {END_DATE}")
    lines.append(f"- **候选股数**: {len(load_candidates())} 只（PE<20 & 股息率≥3% 的价值股 + 主要蓝筹）")
    lines.append(f"- **成功加载**: {total_stocks} 只（K线数据≥120个交易日）")
    lines.append(f"- **触发交易**: {traded_count} 只")
    lines.append(f"- **未触发**: {len(no_trade)} 只")
    lines.append("")

    lines.append("## 三、总体业绩")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    for k, v in overall.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## 四、个股明细（有交易）")
    lines.append("")
    if traded:
        lines.append(f"共 **{traded_count}** 只股票触发了交易：")
        lines.append("")
        lines.append("| # | 代码 | 股票 | 总收益率 | 最大回撤 | 胜率 | 交易次数 | 盈亏比 | 平均耗时 | 盈利耗时 |")
        lines.append("|---|------|------|----------|----------|------|----------|--------|----------|----------|")
        for i, s in enumerate(traded, 1):
            lines.append(
                f"| {i} | {s.get('代码','')} | {s.get('股票','')} "
                f"| {s.get('总收益率','')} | {s.get('最大回撤','')} "
                f"| {s.get('回测胜率','')} | {s.get('交易次数',0)} "
                f"| {s.get('盈亏比','')} | {s.get('平均时间','')} "
                f"| {s.get('盈利耗时','')} |"
            )
        lines.append("")

        # 盈亏统计
        lines.append("### 盈亏分布")
        lines.append("")
        lines.append(f"- 盈利股票: **{len(profit_stocks)}** 只")
        lines.append(f"- 亏损股票: **{len(loss_stocks)}** 只")
        lines.append(f"- 持平股票: **{len(zero_stocks)}** 只")
        if traded_count > 0:
            win_rate = len(profit_stocks) / traded_count * 100
            lines.append(f"- 个股胜率: **{win_rate:.1f}%**")
        lines.append("")

        if profit_stocks:
            top3 = profit_stocks[:3]
            lines.append("**收益最高 TOP 3:**")
            for s in top3:
                lines.append(f"- {s.get('股票','')} ({s.get('代码','')}) — {s.get('总收益率','')}")
            lines.append("")

        if loss_stocks:
            bot3 = sorted(loss_stocks, key=lambda s: parse_pct(s.get('总收益率', 0)))[:3]
            lines.append("**亏损最大 TOP 3:**")
            for s in bot3:
                lines.append(f"- {s.get('股票','')} ({s.get('代码','')}) — {s.get('总收益率','')}")
            lines.append("")
    else:
        lines.append("无股票触发交易。")
        lines.append("")

    lines.append("## 五、未触发交易的股票")
    lines.append("")
    if no_trade:
        lines.append(f"共 {len(no_trade)} 只候选股在2022年未触发入场条件（价格始终高于 MA120 × 88%）：")
        lines.append("")
        names = [f"{s.get('股票','')}({s.get('代码','')})" for s in no_trade]
        # 每行10只
        for i in range(0, len(names), 10):
            lines.append("、".join(names[i:i+10]))
        lines.append("")
    else:
        lines.append("所有候选股均触发了交易。")
        lines.append("")

    lines.append("## 六、结论")
    lines.append("")
    total_return = overall.get('总收益率', 'N/A')
    max_dd = overall.get('最大回撤', 'N/A')
    lines.append(f"2022年A股整体走势偏弱（上证指数全年下跌约15%），市场经历了多次深度调整。")
    lines.append(f"在此背景下，白马梯级策略的表现：")
    lines.append(f"")
    lines.append(f"- **总收益率**: {total_return}")
    lines.append(f"- **最大回撤**: {max_dd}")
    lines.append(f"- **整体胜率**: {overall.get('整体胜率', 'N/A')}")
    lines.append(f"- **总交易次数**: {overall.get('总交易次数', 'N/A')}")
    lines.append("")
    lines.append("策略通过深度回调入场 + 梯级加仓 + 反弹止盈的逻辑，在熊市中寻找结构性机会。")
    lines.append("")
    lines.append("---")
    lines.append("*本报告由回测系统自动生成，仅供研究参考，不构成投资建议。*")

    report_path = os.path.join(os.path.dirname(__file__), "2022年回测报告.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n报告已保存到: {report_path}")


if __name__ == "__main__":
    run()
