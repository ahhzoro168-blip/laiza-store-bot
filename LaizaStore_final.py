from database import conn, cursor, init_db
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import sqlite3
import os

TOKEN = os.getenv("TOKEN")

# 👑 OWNER + FAMILY IDS
OWNER_ID = 6178165984
ALLOWED_USERS = [OWNER_ID, 1465920098]

def is_allowed(user_id):
    return user_id in ALLOWED_USERS

# ===== DATABASE =====
conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, file_id TEXT, price TEXT, category_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS sizes (id INTEGER PRIMARY KEY, product_id INTEGER, size TEXT, stock INTEGER)")
conn.commit()

# ===== GRID =====
def build_grid(items, prefix, page=0, per_page=6, per_row=2):
    start = page * per_page
    end = start + per_page
    sliced = items[start:end]

    keyboard, row = [], []

    for i, (item_id, name) in enumerate(sliced):
        row.append(InlineKeyboardButton(name, callback_data=f"{prefix}_{item_id}"))
        if (i + 1) % per_row == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"{prefix}_page_{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}_page_{page+1}"))
    if nav:
        keyboard.append(nav)

    return InlineKeyboardMarkup(keyboard)

# ===== SIZE BUTTONS =====
def build_size_buttons(pid):
    cursor.execute("SELECT size, stock FROM sizes WHERE product_id=?", (pid,))
    sizes = cursor.fetchall()

    buttons, row = [], []

    for s, st in sizes:
        label = f"{s} ({st})" if st > 0 else f"{s} (0) ❌"
        callback = f"buy_{pid}_{s}" if st > 0 else "no_stock"

        row.append(InlineKeyboardButton(label, callback_data=callback))

        if len(row) == 4:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)

# ===== STOCK BUTTONS =====
def build_stock_buttons(pid):
    cursor.execute("SELECT size, stock FROM sizes WHERE product_id=?", (pid,))
    sizes = cursor.fetchall()

    buttons = []

    for s, st in sizes:
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"minus_{pid}_{s}"),
            InlineKeyboardButton(f"{s} ({st})", callback_data="no_action"),
            InlineKeyboardButton("➕", callback_data=f"plus_{pid}_{s}"),
            InlineKeyboardButton("🗑", callback_data=f"delete_{pid}_{s}")
        ])

    # add size button at bottom (fixed)
    buttons.append([
        InlineKeyboardButton("➕ Add Size", callback_data=f"addsize_{pid}")
    ])

    return InlineKeyboardMarkup(buttons)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_allowed(user_id):
        keyboard = [
            [KeyboardButton("🛍 Shop")],
            [KeyboardButton("⚙️ Manage")]
        ]
    else:
        keyboard = [[KeyboardButton("🛍 Shop")]]

    await update.message.reply_text(
        "✨ Welcome to Laiza Store\n\nClick Shop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== BUTTON CLICK =====
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ===== CATEGORY =====
    if data.startswith("cat_page_"):
        page = int(data.split("_")[2])
        cursor.execute("SELECT * FROM categories")
        await query.message.edit_reply_markup(reply_markup=build_grid(cursor.fetchall(), "cat", page))

    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
        products = cursor.fetchall()

        if not products:
            await query.answer("No products ❌", show_alert=True)
            return

        for pid, file_id, price, _ in products:
            await query.message.reply_photo(
                photo=file_id,
                caption=f"💲 {price}",
                reply_markup=build_size_buttons(pid)
            )

    # ===== BUY =====
    elif data.startswith("buy_"):
        _, pid, size = data.split("_")

        cursor.execute("SELECT stock FROM sizes WHERE product_id=? AND size=?", (pid, size))
        stock = cursor.fetchone()

        if not stock or stock[0] <= 0:
            await query.answer("Out of stock ❌", show_alert=True)
            return

        cursor.execute("UPDATE sizes SET stock=stock-1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()

        await query.answer("✅ Order Complete")

        try:
            await query.message.edit_reply_markup(reply_markup=build_size_buttons(pid))
        except:
            pass

    elif data == "no_stock":
        await query.answer("Out of stock ❌", show_alert=True)

    elif data == "no_action":
        await query.answer()

    # ===== ADD PRODUCT =====
    elif data.startswith("addcat_"):
        context.user_data["category_id"] = data.split("_")[1]
        context.user_data["step"] = "photo"
        await query.message.reply_text("📸 Send product image")

    # ===== STOCK =====
    elif data.startswith("stockcat_"):
        cat_id = data.split("_")[1]
        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))

        for pid, file_id, price, _ in cursor.fetchall():
            keyboard = list(build_stock_buttons(pid).inline_keyboard)
            keyboard.append([
                InlineKeyboardButton("🗑 Delete Product", callback_data=f"deleteproduct_{pid}")
            ])

            await query.message.reply_photo(
                photo=file_id,
                caption=f"📦 Stock Manager\n💲 {price}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ===== STOCK ACTION =====
    elif data.startswith("plus_"):
        _, pid, size = data.split("_")
        cursor.execute("UPDATE sizes SET stock=stock+1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        await query.message.edit_reply_markup(reply_markup=build_stock_buttons(pid))

    elif data.startswith("minus_"):
        _, pid, size = data.split("_")
        cursor.execute("UPDATE sizes SET stock=MAX(stock-1,0) WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        await query.message.edit_reply_markup(reply_markup=build_stock_buttons(pid))

    elif data.startswith("delete_"):
        _, pid, size = data.split("_")
        cursor.execute("DELETE FROM sizes WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        await query.message.edit_reply_markup(reply_markup=build_stock_buttons(pid))

    elif data.startswith("deleteproduct_"):
        pid = data.split("_")[1]
        cursor.execute("DELETE FROM sizes WHERE product_id=?", (pid,))
        cursor.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        await query.message.delete()

    elif data.startswith("addsize_"):
        context.user_data["step"] = "add_size"
        context.user_data["product_id"] = data.split("_")[1]
        await query.message.reply_text("Send size and stock (example: 42:5)")

# ===== TEXT =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    step = context.user_data.get("step")

    if step == "add_cat":
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (text,))
        conn.commit()
        context.user_data.clear()
        await update.message.reply_text("✅ Category added")

    elif step == "price":
        if "file_id" not in context.user_data:
            await update.message.reply_text("❌ Send image first")
            return

        context.user_data["price"] = text
        context.user_data["step"] = "sizes"
        await update.message.reply_text("Send sizes like 40:2,41:1")

    elif step == "sizes":
        cursor.execute(
            "INSERT INTO products (file_id, price, category_id) VALUES (?,?,?)",
            (context.user_data["file_id"], context.user_data["price"], context.user_data["category_id"])
        )
        pid = cursor.lastrowid

        for item in text.split(","):
            s, st = item.split(":")
            cursor.execute("INSERT INTO sizes (product_id, size, stock) VALUES (?,?,?)",
                           (pid, s, int(st)))

        conn.commit()
        context.user_data.clear()
        await update.message.reply_text("✅ Product added")

    elif step == "add_size":
        try:
            size, stock = text.split(":")
            pid = context.user_data["product_id"]
            cursor.execute("INSERT INTO sizes (product_id, size, stock) VALUES (?,?,?)",
                           (pid, size, int(stock)))
            conn.commit()
            context.user_data.clear()
            await update.message.reply_text("✅ Size added")
        except:
            await update.message.reply_text("❌ Format: 42:5")

    elif text == "🛍 Shop":
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text("Choose category", reply_markup=build_grid(cursor.fetchall(), "cat"))

    elif text == "⚙️ Manage":
        keyboard = [
            [KeyboardButton("➕ Add Product")],
            [KeyboardButton("📁 Add Category")],
            [KeyboardButton("📦 Stock")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text("Admin Menu", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    elif text == "➕ Add Product":
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text("Choose category", reply_markup=build_grid(cursor.fetchall(), "addcat"))

    elif text == "📁 Add Category":
        context.user_data["step"] = "add_cat"
        await update.message.reply_text("Send category name")

    elif text == "📦 Stock":
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text("Stock", reply_markup=build_grid(cursor.fetchall(), "stockcat"))

    elif text == "🔙 Back":
        await start(update, context)

# ===== PHOTO =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "photo":
        return

    context.user_data["file_id"] = update.message.photo[-1].file_id
    context.user_data["step"] = "price"
    await update.message.reply_text("Send price")

# ===== RUN =====
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
