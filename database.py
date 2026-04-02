import sqlite3

# اتصال قاعدة البيانات (connection)
conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول
def init_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            file_id TEXT,
            price TEXT,
            category_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sizes (
            id INTEGER PRIMARY KEY,
            product_id INTEGER,
            size TEXT,
            stock INTEGER
        )
    """)

    conn.commit()