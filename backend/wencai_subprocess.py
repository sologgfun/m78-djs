"""
pywencai 子进程隔离调用

PyMiniRacer (V8) 的 address_pool_manager 不支持多线程。
如果主进程加载了 pywencai，后续任何 ThreadPoolExecutor 都会导致 V8 崩溃。
解决方案：在独立子进程中执行 pywencai.get()，主进程通过 JSON 通信获取结果。
"""
import subprocess
import sys
import json
import os
import tempfile

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)


def wencai_get(question, query_type='stock', loop=True, timeout=60):
    """
    在子进程中调用 pywencai.get()，返回 DataFrame 或 None。
    """
    import pandas as pd

    loop_py = "True" if loop else "False"
    script = f"""
import sys, json, os
sys.path.insert(0, {json.dumps(_PROJECT_ROOT)})
import pywencai
import pandas as pd

res = pywencai.get(question={json.dumps(question)}, query_type={json.dumps(query_type)}, loop={loop_py})

# 提取 DataFrame
df = None
if isinstance(res, pd.DataFrame):
    df = res
elif isinstance(res, dict):
    for v in res.values():
        if isinstance(v, pd.DataFrame):
            df = v
            break

if df is not None and len(df) > 0:
    print(df.to_json(orient='split', force_ascii=False))
else:
    print('__EMPTY__')
"""
    try:
        python_exe = sys.executable
        result = subprocess.run(
            [python_exe, '-c', script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=_PROJECT_ROOT,
        )

        stdout = result.stdout.strip()
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(f"[wencai_subprocess] 子进程退出码 {result.returncode}: {stderr[-500:]}")
            return None

        if not stdout or stdout == '__EMPTY__':
            return None

        last_line = stdout.split('\n')[-1]
        from io import StringIO
        df = pd.read_json(StringIO(last_line), orient='split')
        return df

    except subprocess.TimeoutExpired:
        print(f"[wencai_subprocess] 超时 ({timeout}s): {question[:50]}")
        return None
    except Exception as e:
        print(f"[wencai_subprocess] 异常: {e}")
        return None
