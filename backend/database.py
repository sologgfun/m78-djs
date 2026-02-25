"""
数据库管理模块 - 使用SQLite
"""
import sqlite3
import json
from datetime import datetime
import os
import math
from typing import Any


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path='backend/backtest.db'):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()
    
    def _ensure_dir(self):
        """确保目录存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                batch_id TEXT,
                name TEXT,
                stock_codes TEXT,
                start_date TEXT,
                end_date TEXT,
                initial_capital REAL,
                max_positions INTEGER,
                config_type TEXT,
                status TEXT,
                progress REAL,
                message TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                strategy TEXT,
                mode TEXT,
                screen_params TEXT
            )
        """)

        # 自动迁移：为旧表补充缺失的列
        existing = {row[1] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()}
        for col, col_type in [
            ('strategy', 'TEXT'), ('mode', 'TEXT'), ('screen_params', 'TEXT'),
            ('user_id', 'INTEGER'), ('is_public', 'INTEGER DEFAULT 0'),
        ]:
            col_name = col.split()[0] if ' ' in col else col
            if col_name not in existing:
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col} {col_type}")

        # 创建用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT
            )
        """)
        
        # 创建结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                task_id TEXT PRIMARY KEY,
                overall_stats TEXT,
                stock_results TEXT,
                trades TEXT,
                daily_stats TEXT,
                created_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        """)
        
        conn.commit()
        conn.close()

    def _sanitize_json_value(self, value: Any):
        """递归清理 NaN/Inf 与 numpy 标量，确保可 JSON 序列化"""
        # numpy 标量（np.int64/np.float64/np.bool_ 等）转换为 Python 原生类型
        try:
            import numpy as np  # 项目内已依赖 numpy
            if isinstance(value, (np.integer, np.floating, np.bool_)):
                return self._sanitize_json_value(value.item())
        except Exception:
            pass

        if isinstance(value, float):
            if not math.isfinite(value):
                return None
            return value
        # datetime 兜底（避免某些字段被直接塞进结果里）
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: self._sanitize_json_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_json_value(v) for v in value]
        return value

    def _safe_json_dumps(self, data):
        """安全序列化 JSON，避免 NaN/Inf 导致失败"""
        sanitized = self._sanitize_json_value(data)
        return json.dumps(sanitized, ensure_ascii=False)
    
    def save_task(self, task):
        """保存任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO tasks 
            (task_id, batch_id, name, stock_codes, start_date, end_date, 
             initial_capital, max_positions, config_type, status, progress, 
             message, created_at, started_at, completed_at, strategy,
             user_id, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task['task_id'],
            task.get('batch_id'),
            task['name'],
            json.dumps(task['stock_codes']),
            task['start_date'],
            task['end_date'],
            task['initial_capital'],
            task['max_positions'],
            task['config_type'],
            task['status'],
            task.get('progress', 0),
            task.get('message', ''),
            task['created_at'],
            task.get('started_at'),
            task.get('completed_at'),
            json.dumps(task.get('strategy')) if task.get('strategy') else None,
            task.get('user_id'),
            1 if task.get('is_public') else 0
        ))
        
        conn.commit()
        conn.close()
    
    def update_task_status(self, task_id, status, progress=None, message=None):
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = ['status = ?']
        params = [status]
        
        if progress is not None:
            updates.append('progress = ?')
            params.append(progress)
        
        if message is not None:
            updates.append('message = ?')
            params.append(message)
        
        if status == 'running':
            updates.append('started_at = ?')
            params.append(datetime.now().isoformat())
        elif status in ['completed', 'failed']:
            updates.append('completed_at = ?')
            params.append(datetime.now().isoformat())
        
        params.append(task_id)
        
        cursor.execute(f"""
            UPDATE tasks 
            SET {', '.join(updates)}
            WHERE task_id = ?
        """, params)
        
        conn.commit()
        conn.close()
    
    def update_task_name(self, task_id, name):
        """更新任务名称"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tasks SET name = ? WHERE task_id = ?
        """, (name, task_id))
        
        conn.commit()
        conn.close()
    
    def save_result(self, task_id, results):
        """保存回测结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO results 
            (task_id, overall_stats, stock_results, trades, daily_stats, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            self._safe_json_dumps(results.get('overall_stats', {})),
            self._safe_json_dumps(results.get('stock_results', [])),
            self._safe_json_dumps(results.get('trades', [])),
            self._safe_json_dumps(results.get('daily_stats', [])),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_task(self, task_id):
        """获取任务"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            task = dict(row)
            task['stock_codes'] = json.loads(task['stock_codes'])
            if task.get('strategy'):
                try:
                    task['strategy'] = json.loads(task['strategy'])
                except:
                    pass
            return task
        return None
    
    def get_all_tasks(self, limit=100, user_id=None):
        """获取任务列表。已登录用户看到自己的任务+公开任务；访客只看公开任务。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if user_id is not None:
            cursor.execute("""
                SELECT * FROM tasks
                WHERE user_id = ? OR is_public = 1
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM tasks
                WHERE is_public = 1
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            task = dict(row)
            task['stock_codes'] = json.loads(task['stock_codes'])
            if task.get('strategy'):
                try:
                    task['strategy'] = json.loads(task['strategy'])
                except:
                    pass
            tasks.append(task)
        
        return tasks
    
    def get_result(self, task_id):
        """获取结果"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM results WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            result = {
                'task_id': row['task_id'],
                'overall_stats': self._sanitize_json_value(json.loads(row['overall_stats'])),
                'stock_results': self._sanitize_json_value(json.loads(row['stock_results'])),
                'trades': self._sanitize_json_value(json.loads(row['trades'])),
                'daily_stats': self._sanitize_json_value(json.loads(row['daily_stats'])),
                'created_at': row['created_at']
            }
            return result
        return None
    
    def get_batch_results(self, batch_id):
        """获取批量回测结果"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.*, r.overall_stats 
            FROM tasks t
            LEFT JOIN results r ON t.task_id = r.task_id
            WHERE t.batch_id = ?
            ORDER BY t.created_at
        """, (batch_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            result = dict(row)
            result['stock_codes'] = json.loads(result['stock_codes'])
            if result['overall_stats']:
                result['overall_stats'] = self._sanitize_json_value(json.loads(result['overall_stats']))
            results.append(result)
        
        return results
    
    def delete_task(self, task_id):
        """删除任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM results WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        
        conn.commit()
        conn.close()
    
    def get_summary(self):
        """获取统计摘要"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        completed_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'running'")
        running_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        pending_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'failed'")
        failed_tasks = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_tasks': total_tasks,
            'completed': completed_tasks,
            'running': running_tasks,
            'pending': pending_tasks,
            'failed': failed_tasks
        }

    # ==================== 用户相关 ====================

    def create_user(self, username, password_hash):
        """创建用户，返回 user_id；用户名已存在时返回 None"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
            """, (username, password_hash, datetime.now().isoformat()))
            conn.commit()
            uid = cursor.lastrowid
            return uid
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username):
        """按用户名查找用户"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_id(self, user_id):
        """按 id 查找用户"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
