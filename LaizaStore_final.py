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

conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(...)
conn.commit()

import os
TOKEN = os.getenv("TOKEN")

# 👑 OWNER + FAMILY IDS
OWNER_ID = 6178165984
ALLOWED_USERS = [
    OWNER_ID,
    1465920098
]

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
def build_grid(items, prefix, page=0, per_page=6, per_row=3):
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
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_page_{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_page_{page+1}"))

    if nav:
        keyboard.append(nav)

    return InlineKeyboardMarkup(keyboard)

def build_grid(items, prefix, page=0, per_page=6, per_row=2):
    start = page * per_page
    end = start + per_page
    sliced = items[start:end]

    keyboard = []
    row = []

    # ===== GRID (3x3) =====
    for i, (item_id, name) in enumerate(sliced):
        row.append(InlineKeyboardButton(name, callback_data=f"{prefix}_{item_id}"))

        if (i + 1) % per_row == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # ===== NAVIGATION =====
    nav = []

    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"{prefix}_page_{page-1}"))

    if end < len(items):
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}_page_{page+1}"))

    # ALWAYS show nav if exist
    if nav:
        keyboard.append(nav)

    return InlineKeyboardMarkup(keyboard)
    
# ===== SIZE BUTTONS =====
def build_size_buttons(pid):
    cursor.execute("SELECT size, stock FROM sizes WHERE product_id=?", (pid,))
    sizes = cursor.fetchall()

    buttons, row = [], []

    for s, st in sizes:
        if st > 0:
            label = f"{s} ({st})"
            callback = f"buy_{pid}_{s}"
        else:
            label = f"{s} (0) ❌"
            callback = "no_stock"

        row.append(InlineKeyboardButton(label, callback_data=callback))

        if len(row) == 4:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)

# ===== STOCK buttons =====
def build_stock_buttons(pid):
    cursor.execute("SELECT size, stock FROM sizes WHERE product_id=?", (pid,))
    sizes = cursor.fetchall()

    buttons = []

    for s, st in sizes:
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"minus_{pid}_{s}"),
            InlineKeyboardButton(f"{s} ({st})", callback_data="no_action"),
            InlineKeyboardButton("➕", callback_data=f"plus_{pid}_{s}")
        ])

    return InlineKeyboardMarkup(buttons)

# ===== build_stock_buttons =====
def build_stock_buttons(pid):
    cursor.execute("SELECT size, stock FROM sizes WHERE product_id=?", (pid,))
    sizes = cursor.fetchall()

    buttons = []

    for s, st in sizes:
        buttons.append([
            InlineKeyboardButton("➖", callback_data=f"minus_{pid}_{s}"),
            InlineKeyboardButton(f"{s} ({st})", callback_data="no_action"),
            InlineKeyboardButton("➕", callback_data=f"plus_{pid}_{s}"),
            InlineKeyboardButton("🗑", callback_data=f"delete_{pid}_{s}"),
            InlineKeyboardButton("🔅", callback_data=f"addsize_{pid}")
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
        keyboard = [
            [KeyboardButton("🛍 Shop")]
        ]

    await update.message.reply_text(
        "✨ Welcome\n\nChoose:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== BUTTON =====
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ===== CATEGORY VIEW =====
    if data.startswith("cat_page_"):
        page = int(data.split("_")[2])
        cursor.execute("SELECT * FROM categories")
        markup = build_grid(cursor.fetchall(), "cat", page)
        await query.message.edit_reply_markup(reply_markup=markup)

    # ✅ THEN (normal click)
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]

    # ===== BUY =====
    elif data.startswith("buy_"):
        _, pid, size = data.split("_")

        cursor.execute(
            "SELECT stock FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        result = cursor.fetchone()

        if not result or result[0] <= 0:
            await query.answer("Out of stock ❌", show_alert=True)
            return

        cursor.execute(
            "UPDATE sizes SET stock=stock-1 WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        cursor.execute(
            "SELECT stock FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        new_stock = cursor.fetchone()[0]

        await query.answer("✅ Order Complete")

        try:
            await query.message.edit_reply_markup(
                reply_markup=build_size_buttons(pid)
            )
        except:
            pass

        await query.message.reply_text(
            f"✅ Order Complete!\n\n"
            f"👟 Size: {size}\n"
            f"📦 Remaining: {new_stock}"
        )

    # 🚫 NO STOCK
    elif data == "no_stock":
        await query.answer("Out of stock ❌", show_alert=True)

    # ===== ADMIN CALLBACK =====
    elif data.startswith("addcat_") or data.startswith("delcat_"):
        user_id = query.from_user.id
        if not is_allowed(user_id):
            await query.answer("🚫 Not allowed", show_alert=True)
            return

        if data.startswith("addcat_"):
            context.user_data["category_id"] = data.split("_")[1]
            context.user_data["step"] = "photo"
            await query.message.reply_text("📸 Send image")

        elif data.startswith("delcat_"):
            cid = data.split("_")[1]
            cursor.execute("DELETE FROM categories WHERE id=?", (cid,))
            cursor.execute("DELETE FROM products WHERE category_id=?", (cid,))
            conn.commit()
            await query.message.reply_text("🗑 Deleted")

    # ===== STOCK CATEGORY =====
    elif data.startswith("stockcat_"):
        cat_id = data.split("_")[1]

        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
        for pid, file_id, price, _ in cursor.fetchall():

            keyboard = list(build_stock_buttons(pid).inline_keyboard)

            # add delete product button at bottom
            keyboard.append([
                InlineKeyboardButton("🗑 Delete Product", callback_data=f"deleteproduct_{pid}")
            ])

            await query.message.reply_photo(
                photo=file_id,
                caption=f"📦 Stock Manager\n💲 {price}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ===== Add ➕ / ➖ logic =====
    elif data.startswith("plus_"):
        _, pid, size = data.split("_")

        cursor.execute(
            "UPDATE sizes SET stock = stock + 1 WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        await query.answer("➕ Added")

        await query.message.edit_reply_markup(
            reply_markup=build_stock_buttons(pid)
        )

    elif data.startswith("minus_"):
        _, pid, size = data.split("_")

        cursor.execute(
            "SELECT stock FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        stock = cursor.fetchone()[0]

        if stock <= 0:
            await query.answer("Already 0 ❌", show_alert=True)
            return

        cursor.execute(
            "UPDATE sizes SET stock = stock - 1 WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        await query.answer("➖ Reduced")

        await query.message.edit_reply_markup(
            reply_markup=build_stock_buttons(pid)
        )

    elif data == "no_action":
        await query.answer()

    # ===== DELETE =====
    elif data.startswith("delete_"):
        _, pid, size = data.split("_")

        # delete that size
        cursor.execute(
            "DELETE FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        await query.answer("🗑 Deleted")

        # update UI
        await query.message.edit_reply_markup(
            reply_markup=build_stock_buttons(pid)
        )

    # ===== Delete Product =====
    elif data.startswith("deleteproduct_"):
        pid = data.split("_")[1]

        # delete sizes first
        cursor.execute("DELETE FROM sizes WHERE product_id=?", (pid,))
    
        # delete product
        cursor.execute("DELETE FROM products WHERE id=?", (pid,))
    
        conn.commit()

        await query.answer("🗑 Product Deleted")

        await query.message.delete()

    # ===== Delete Product =====
    elif data.startswith("addsize_"):
        pid = data.split("_")[1]

        context.user_data["step"] = "add_size"
        context.user_data["product_id"] = pid

        await query.message.reply_text("Send size and stock\nExample: 42:5")

    # ===== ADD CATEGORY PAGINATION =====
    elif data.startswith("addcat_page_"):
        page = int(data.split("_")[2])

        cursor.execute("SELECT * FROM categories")
        markup = build_grid(cursor.fetchall(), "addcat", page)

        await query.message.edit_reply_markup(reply_markup=markup)

    # ===== SELECT CATEGORY (ADD PRODUCT) =====
    elif data.startswith("addcat_"):
        cat_id = data.split("_")[1]

        context.user_data["category_id"] = cat_id
        context.user_data["step"] = "photo"

        await query.message.reply_text("📸 Send product image")

# ===== TEXT =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    step = context.user_data.get("step")

    if not is_allowed(user_id):
        if text != "🛍 Shop":
            await update.message.reply_text("🚫 You can only use Shop")
            return

    if step == "add_cat":
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (text,))
        conn.commit()
        context.user_data.clear()
        await update.message.reply_text("✅ Category added")
        return

    elif step == "price":
        context.user_data["price"] = text
        context.user_data["step"] = "sizes"
        await update.message.reply_text("Send sizes 40:2,41:1")
        return

    elif step == "sizes":
        cursor.execute(
            "INSERT INTO products (file_id, price, category_id) VALUES (?,?,?)",
            (
                context.user_data["file_id"],
                context.user_data["price"],
                context.user_data["category_id"]
            )
        )
        pid = cursor.lastrowid

        for item in text.split(","):
            s, st = item.split(":")
            cursor.execute(
                "INSERT INTO sizes (product_id, size, stock) VALUES (?,?,?)",
                (pid, s, int(st))
            )

        conn.commit()
        context.user_data.clear()

        await update.message.reply_text("✅ Product added")
        keyboard = [
            [KeyboardButton("➕ Add More Product")],
            [KeyboardButton("🔙 Back")]
        ]

        await update.message.reply_text(
            "What's next?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "➕ Add More Product":
        if not is_allowed(user_id):
            await update.message.reply_text("🚫 Not allowed")
            return

        cursor.execute("SELECT * FROM categories")
        cats = cursor.fetchall()

        if not cats:
            await update.message.reply_text("Add category first")
            return

        await update.message.reply_text(
            "Choose category",
            reply_markup=build_grid(cats, "addcat")
        )

    if text == "🛍 Shop":
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text(
            "🛍 Choose Category",
            reply_markup=build_grid(cursor.fetchall(), "cat")
        )

    elif text == "➕ Add":
        if not is_allowed(user_id):
            await update.message.reply_text("🚫 Not allowed")
            return

        keyboard = [
            [KeyboardButton("➕ Add Product")],
            [KeyboardButton("📁 Categories")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text(
            "Admin Menu",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "📁 Categories":
        keyboard = [
            [KeyboardButton("➕ Add Category")],
            [KeyboardButton("🗑 Delete Category")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text(
            "📂 Category Manager",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "➕ Add Category":
        context.user_data["step"] = "add_cat"
        await update.message.reply_text("Send category name")

    elif text == "🗑 Delete Category":
        cursor.execute("SELECT * FROM categories")
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"delcat_{cid}")]
            for cid, name in cursor.fetchall()
        ]
        await update.message.reply_text(
            "Choose:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif text == "➕ Add Product":
        cursor.execute("SELECT * FROM categories")
        cats = cursor.fetchall()

        if not cats:
            await update.message.reply_text("Add category first")
            return

        await update.message.reply_text(
            "Choose category",
            reply_markup=build_grid(cats, "addcat")
        )

    elif text == "⚙️ Manage":
        if not is_allowed(user_id):
            await update.message.reply_text("🚫 Not allowed")
            return

        keyboard = [
            [KeyboardButton("➕ Add")],
            [KeyboardButton("📦 Stock")],
            [KeyboardButton("🔙 Back")]
        ]
        await update.message.reply_text(
            "⚙️ Manage",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "📦 Stock":
        if not is_allowed(user_id):
            await update.message.reply_text("🚫 Not allowed")
            return

        cursor.execute("SELECT * FROM categories")

        await update.message.reply_text(
            "📦 Stock (Select Category)",
            reply_markup=build_grid(cursor.fetchall(), "stockcat")
        )

    elif step == "add_size":
        try:
            size, stock = text.split(":")
            pid = context.user_data["product_id"]

            cursor.execute(
                "INSERT INTO sizes (product_id, size, stock) VALUES (?,?,?)",
                (pid, size, int(stock))
            )
            conn.commit()

            context.user_data.clear()

            await update.message.reply_text(f"✅ Size {size} added with stock {stock}")

        except:
            await update.message.reply_text("❌ Format error. Use: 42:5")

    elif text == "🔙 Back":
        await start(update, context)

# ===== PHOTO =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
