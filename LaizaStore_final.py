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
def build_grid(items, prefix, page=0, per_page=6, per_row=2):
    start = page * per_page
    end = start + per_page
    sliced = items[start:end]

    keyboard = []
    row = []

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
        "✨ Welcome to Laiza Store\n\nPlease Click on Shop:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== BUTTON =====
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ===== PAGINATION FIRST =====
    if data.startswith("cat_page_"):
        page = int(data.split("_")[2])
        cursor.execute("SELECT * FROM categories")
        await query.message.edit_reply_markup(
            reply_markup=build_grid(cursor.fetchall(), "cat", page)
        )
        return

    elif data.startswith("stockcat_page_"):
        page = int(data.split("_")[2])
        cursor.execute("SELECT * FROM categories")
        await query.message.edit_reply_markup(
            reply_markup=build_grid(cursor.fetchall(), "stockcat", page)
        )
        return

    elif data.startswith("addcat_page_"):
        page = int(data.split("_")[2])
        cursor.execute("SELECT * FROM categories")
        await query.message.edit_reply_markup(
            reply_markup=build_grid(cursor.fetchall(), "addcat", page)
        )
        return

    # ===== CATEGORY VIEW =====
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]

        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
        products = cursor.fetchall()

        if not products:
            await query.answer("No products ❌", show_alert=True)
            return

        for product_id, file_id, price, _ in products:
            await query.message.reply_photo(
                photo=file_id,
                caption=f"Price: {price}\n────────────\nSelect Size:",
                reply_markup=build_size_buttons(product_id)
            )
        return

    # ===== BUY =====
    elif data.startswith("buy_"):
        _, pid, size = data.split("_")

        user = query.from_user
        user_name = user.full_name
        user_id = user.id

        # get stock
        cursor.execute(
            "SELECT stock FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        result = cursor.fetchone()

        if not result or result[0] <= 0:
            await query.answer("Out of stock ❌", show_alert=True)
            return

        # reduce stock
        cursor.execute(
            "UPDATE sizes SET stock=stock-1 WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        # get updated stock
        cursor.execute(
            "SELECT stock FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        new_stock = cursor.fetchone()[0]

        # get product price
        cursor.execute(
            "SELECT price FROM products WHERE id=?",
            (pid,)
        )
        price = cursor.fetchone()[0]

        await query.answer("✅ Order Complete")

        # update UI
        await query.message.edit_reply_markup(
            reply_markup=build_size_buttons(pid)
        )

        # ===== SEND TO USER =====
        await query.message.reply_text(
            f"✅ Order Complete!\n\n"
            f"👟 Size: {size}\n"
            f"💰 Price: {price}\n"
            f"📦 Remaining: {new_stock}"
        )

        # ===== 🔔 SEND TO OWNER =====
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    "🛒 *NEW ORDER*\n\n"
                    f"👤 User: {user_name}\n"
                    f"🆔 ID: `{user_id}`\n\n"
                    f"👟 Product ID: {pid}\n"
                    f"📏 Size: {size}\n"
                    f"💰 Price: {price}\n\n"
                    f"📦 Remaining: {new_stock}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            print("Notify error:", e)

    elif data == "no_stock":
        await query.answer("Out of stock ❌", show_alert=True)
        return

    # ===== STOCK CATEGORY =====
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
        return

    # ===== STOCK CONTROL =====
    elif data.startswith("plus_"):
        _, pid, size = data.split("_")

        cursor.execute(
            "UPDATE sizes SET stock = stock + 1 WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        await query.message.edit_reply_markup(
            reply_markup=build_stock_buttons(pid)
        )
        return

    elif data.startswith("minus_"):
        _, pid, size = data.split("_")

        cursor.execute(
            "UPDATE sizes SET stock = MAX(stock - 1, 0) WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        await query.message.edit_reply_markup(
            reply_markup=build_stock_buttons(pid)
        )
        return

    elif data.startswith("deletesize_"):   # ✅ renamed
        _, pid, size = data.split("_")

        cursor.execute(
            "DELETE FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()

        await query.message.edit_reply_markup(
            reply_markup=build_stock_buttons(pid)
        )
        return

    elif data.startswith("deleteproduct_"):
        pid = data.split("_")[1]

        cursor.execute("DELETE FROM sizes WHERE product_id=?", (pid,))
        cursor.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()

        await query.message.delete()
        return

    elif data.startswith("addsize_"):
        pid = data.split("_")[1]

        context.user_data["step"] = "add_size"
        context.user_data["product_id"] = pid

        await query.message.reply_text("Send size and stock\nExample: 42:5")
        return

    # ===== ADD PRODUCT =====
    elif data.startswith("addcat_"):
        cat_id = data.split("_")[1]

        context.user_data["category_id"] = cat_id
        context.user_data["step"] = "photo"

        await query.message.reply_text("📸 Send product image")
        return

    # ===== DELETE CATEGORY =====
    elif data.startswith("delcat_"):
        cid = data.split("_")[1]

        cursor.execute("DELETE FROM categories WHERE id=?", (cid,))
        cursor.execute("DELETE FROM products WHERE category_id=?", (cid,))
        conn.commit()

        await query.message.reply_text("🗑 Deleted")
        return

    elif data == "no_action":
        await query.answer()


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
            "🔎 Find Shose Mode that you want",
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
            "🫂 Admin Menu",
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
            "Choose option:",
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
