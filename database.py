import sqlite3

# Connect to database
conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

# ================= CATEGORIES =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")

# ================= PRODUCTS =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    price TEXT,
    category_id INTEGER,
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
""")

# ================= SIZES =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS sizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    size TEXT,
    stock INTEGER,
    FOREIGN KEY (product_id) REFERENCES products(id)
)
""")

# ================= ORDERS =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    name TEXT,
    product_id INTEGER,
    size TEXT,
    price TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ================= DEFAULT DATA =================
cursor.execute("""
INSERT OR IGNORE INTO categories (id, name)
VALUES (1, 'Shoes')
""")


# Save changes
conn.commit()