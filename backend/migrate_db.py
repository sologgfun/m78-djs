import sqlite3
import os

DB_PATH = 'backtest.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if 'strategy' column exists
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'strategy' not in columns:
            print("Adding 'strategy' column to tasks table...")
            cursor.execute("ALTER TABLE tasks ADD COLUMN strategy TEXT")
            print("Column added successfully.")
        else:
            print("'strategy' column already exists.")

    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.commit()
        conn.close()

if __name__ == '__main__':
    migrate()
