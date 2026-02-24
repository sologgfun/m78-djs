"""
后端API服务器
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import queue
import uuid
from datetime import datetime
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Database
from backend.backtest_worker import BacktestWorker
from backend.stock_service import StockService

# 生产环境：若 frontend-vite/dist 存在，则由 Flask 托管前端静态资源
FRONTEND_DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend-vite", "dist")
app = Flask(__name__, static_folder=FRONTEND_DIST_DIR if os.path.isdir(FRONTEND_DIST_DIR) else None, static_url_path="/")
CORS(app)  # 允许跨域请求

# 初始化服务
db = Database()
stock_service = StockService()
backtest_queue = queue.Queue()
backtest_worker = BacktestWorker(backtest_queue, db)


# ==================== 股票相关API ====================

@app.route('/api/stocks/list', methods=['GET'])
def get_stock_list():
    """获取股票列表"""
    try:
        stocks = stock_service.get_all_stocks()
        return jsonify({
            'success': True,
            'data': stocks,
            'total': len(stocks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stocks/search', methods=['GET'])
def search_stocks():
    """搜索股票"""
    keyword = request.args.get('keyword', '')
    try:
        stocks = stock_service.search_stocks(keyword)
        return jsonify({
            'success': True,
            'data': stocks,
            'total': len(stocks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stocks/screen', methods=['POST'])
def screen_stocks():
    """筛选符合条件的股票"""
    params = request.json
    try:
        stocks = stock_service.screen_stocks(
            pe_max=params.get('pe_max', 20),
            dividend_min=params.get('dividend_min', 3),
            market_cap_min=params.get('market_cap_min', 0)
        )
        return jsonify({
            'success': True,
            'data': stocks,
            'total': len(stocks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stocks/djs', methods=['GET'])
def get_djs_stocks():
    """获取点金术推荐列表（支持可配置筛选条件）"""
    pe_max = request.args.get('pe_max', 20, type=float)
    dividend_min = request.args.get('dividend_min', 3, type=float)
    price_ratio = request.args.get('price_ratio', 90, type=float)

    stocks = stock_service.get_djs_recommendations(
        pe_max=pe_max,
        dividend_min=dividend_min,
        price_ratio=price_ratio,
    )
    return jsonify({
        'success': True,
        'data': stocks,
        'total': len(stocks)
    })


# ==================== 回测任务API ====================

@app.route('/api/backtest/create', methods=['POST'])
def create_backtest():
    """创建回测任务"""
    try:
        data = request.json
        
        task_id = str(uuid.uuid4())
        task = {
            'task_id': task_id,
            'name': data.get('name', f'回测_{datetime.now().strftime("%Y%m%d_%H%M%S")}'),
            'stock_codes': data.get('stock_codes', []),
            'start_date': data.get('start_date', '2021-01-01'),
            'end_date': data.get('end_date', '2025-12-31'),
            'initial_capital': data.get('initial_capital', 200000),
            'max_positions': data.get('max_positions', 5),
            # 支持前端传入自定义策略参数；兼容旧的 config_type
            'strategy': data.get('strategy', None),
            'config_type': data.get('config_type', 'balanced'),
            'mode': data.get('mode', 'manual'),  # manual or auto_screen
            'screen_params': data.get('screen_params', {}), # e.g. {pe_max: 20, dividend_min: 3}
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        # 保存到数据库
        db.save_task(task)
        
        # 添加到队列
        backtest_queue.put(task)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '回测任务已创建'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/batch', methods=['POST'])
def create_batch_backtest():
    """批量创建回测任务"""
    try:
        data = request.json
        batch_id = str(uuid.uuid4())
        
        stock_codes = data.get('stock_codes', [])
        base_config = data.get('config', {})
        
        task_ids = []
        
        # 为每只股票创建单独的回测任务
        for stock_code in stock_codes:
            task_id = str(uuid.uuid4())
            task = {
                'task_id': task_id,
                'batch_id': batch_id,
                'name': f'{stock_code}_{base_config.get("name", "批量回测")}',
                'stock_codes': [stock_code],
                'start_date': base_config.get('start_date', '2021-01-01'),
                'end_date': base_config.get('end_date', '2025-12-31'),
                'initial_capital': base_config.get('initial_capital', 200000),
                'max_positions': 1,  # 单股票回测
                'strategy': base_config.get('strategy', None),
                'config_type': base_config.get('config_type', 'balanced'),
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            db.save_task(task)
            backtest_queue.put(task)
            task_ids.append(task_id)
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'task_ids': task_ids,
            'total': len(task_ids),
            'message': f'已创建{len(task_ids)}个回测任务'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/tasks', methods=['GET'])
def get_tasks():
    """获取所有回测任务"""
    try:
        tasks = db.get_all_tasks()
        return jsonify({
            'success': True,
            'data': tasks,
            'total': len(tasks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/task/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取单个任务状态"""
    try:
        task = db.get_task(task_id)
        if task:
            return jsonify({
                'success': True,
                'data': task
            })
        else:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/result/<task_id>', methods=['GET'])
def get_result(task_id):
    """获取回测结果"""
    try:
        result = db.get_result(task_id)
        if result:
            # 默认只返回：整体统计 + 股票结果表（避免 payload 过大导致前端/网络不稳定）
            basic = {
                'task_id': result.get('task_id'),
                'overall_stats': result.get('overall_stats', {}),
                'stock_results': result.get('stock_results', []),
                'created_at': result.get('created_at')
            }
            return jsonify({
                'success': True,
                'data': basic
            })
        else:
            return jsonify({
                'success': False,
                'error': '结果不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/result/<task_id>/details', methods=['GET'])
def get_result_details(task_id):
    """获取回测结果详情（全量 trades 和 daily_stats）"""
    try:
        result = db.get_result(task_id)
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'task_id': result.get('task_id'),
                    'daily_stats': result.get('daily_stats', []),
                    'trades': result.get('trades', [])
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': '结果不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/result/<task_id>/trades', methods=['GET'])
def get_result_trades(task_id):
    """获取回测交易明细（可按股票过滤）"""
    try:
        result = db.get_result(task_id)
        if not result:
            return jsonify({'success': False, 'error': '结果不存在'}), 404

        trades = result.get('trades') or []
        stock_code = request.args.get('stock_code')
        
        if stock_code:
            stock_code = str(stock_code)
            trades = [t for t in trades if str(t.get('stock_code', '')) == stock_code]
            
            # 日志：输出过滤后的交易数量和日期范围
            if trades:
                dates = [t['date'] for t in trades if 'date' in t]
                if dates:
                    min_date = min(dates)
                    max_date = max(dates)
                    print(f"[交易明细] {stock_code}: {len(trades)}笔 ({min_date} ~ {max_date})")
                    # 输出买入交易的日期
                    buy_trades = [t for t in trades if t.get('action') == 'BUY']
                    if buy_trades:
                        buy_dates = [t['date'] for t in buy_trades]
                        print(f"  买入: {len(buy_trades)}笔 - {', '.join(sorted(buy_dates))}")

        return jsonify({'success': True, 'data': trades, 'total': len(trades)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backtest/batch/<batch_id>', methods=['GET'])
def get_batch_results(batch_id):
    """获取批量回测结果"""
    try:
        results = db.get_batch_results(batch_id)
        return jsonify({
            'success': True,
            'data': results,
            'total': len(results)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/delete/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除回测任务"""
    try:
        db.delete_task(task_id)
        return jsonify({
            'success': True,
            'message': '任务已删除'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backtest/update/<task_id>', methods=['PUT'])
def update_task(task_id):
    """更新回测任务（名称等）"""
    try:
        data = request.json
        name = data.get('name')
        if name:
            db.update_task_name(task_id, name)
        return jsonify({
            'success': True,
            'message': '任务已更新'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== 统计API ====================

@app.route('/api/stats/summary', methods=['GET'])
def get_summary():
    """获取统计摘要"""
    try:
        summary = db.get_summary()
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 系统API ====================

@app.route('/api/system/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'success': True,
        'status': 'running',
        'worker_alive': backtest_worker.is_alive(),
        'queue_size': backtest_queue.qsize(),
        'timestamp': datetime.now().isoformat()
    })


# ==================== 前端托管（可选） ====================

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    托管前端构建产物（frontend-vite/dist）。
    - 开发模式请使用 Vite： http://127.0.0.1:5173
    - 生产模式 build 后访问： http://127.0.0.1:8000
    """
    # 不拦截 API
    if path.startswith("api/"):
        return jsonify({'success': False, 'error': 'Not Found'}), 404

    if not os.path.isdir(FRONTEND_DIST_DIR):
        return jsonify({
            'success': False,
            'error': '前端未构建。请先在 frontend-vite/ 执行 npm install && npm run build，或使用 npm run dev。'
        }), 404

    # 静态文件优先
    file_path = os.path.join(FRONTEND_DIST_DIR, path)
    if path and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIST_DIR, path)

    # SPA 回退到 index.html
    return send_from_directory(FRONTEND_DIST_DIR, 'index.html')


def main():
    """启动服务器"""
    print("="*70)
    print("白马梯级轮动策略 - 后端服务器")
    print("="*70)
    print("\n正在启动服务...")
    
    # 启动回测工作线程
    backtest_worker.start()
    print("✓ 回测工作线程已启动")
    
    print("\n服务器地址: http://localhost:8000")
    print("API文档: http://localhost:8000/api/docs")
    print("\n按 Ctrl+C 停止服务器")
    print("="*70 + "\n")
    
    try:
        port = int(os.environ.get('PORT', 8000))
        app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        backtest_worker.stop()
        print("服务器已关闭")


if __name__ == '__main__':
    main()
