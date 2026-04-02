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

# 🌐 LANGUAGE SYSTEM
user_lang = {}

LANG = {
    "en": {
        "shop": "🛍 Shop",
        "manage": "⚙️ Manage",
        "back": "🔙 Back",
        "welcome": "✨ Welcome\n\nChoose:",
        "stock": "📦 Stock",
        "add": "➕ Add",
        "add_product": "➕ Add Product",
        "categories": "📁 Categories",
        "add_category": "➕ Add Category",
        "delete_category": "🗑 Delete Category",
        "choose_category": "🛍 Choose Category",
        "select_size": "Select Size:",
        "order_done": "✅ Order Complete!",
        "out_stock": "Out of stock ❌",
        "product_added": "✅ Product added\n\nWhat next?",
        "add_more": "➕ Add More Product",
        "send_price": "Send price",
        "send_sizes": "Send sizes 40:2,41:1"
    },
    "kh": {
        "shop": "🛍 ទិញទំនិញ",
        "manage": "⚙️ គ្រប់គ្រង",
        "back": "🔙 ត្រឡប់ក្រោយ",
        "welcome": "✨ សូមស្វាគមន៍\n\nជ្រើសរើស៖",
        "stock": "📦 ស្តុក",
        "add": "➕ បន្ថែម",
        "add_product": "➕ បន្ថែមផលិតផល",
        "categories": "📁 ប្រភេទ",
        "add_category": "➕ បន្ថែមប្រភេទ",
        "delete_category": "🗑 លុបប្រភេទ",
        "choose_category": "🛍 ជ្រើសរើសប្រភេទ",
        "select_size": "ជ្រើសរើសទំហំ៖",
        "order_done": "✅ បញ្ជាទិញបានជោគជ័យ",
        "out_stock": "អស់ស្តុក ❌",
        "product_added": "✅ បានបន្ថែមផលិតផល\n\nតើបន្ទាប់?",
        "add_more": "➕ បន្ថែមទៀត",
        "send_price": "ផ្ញើតម្លៃ",
        "send_sizes": "ផ្ញើទំហំ 40:2,41:1"
    }
}

# ===== DATABASE =====
conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, file_id TEXT, price TEXT, category_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS sizes (id INTEGER PRIMARY KEY, product_id INTEGER, size TEXT, stock INTEGER)")
conn.commit()

# ===== GRID =====
def build_grid(items, prefix):
    keyboard = []
    for item_id, name in items:
        keyboard.append([InlineKeyboardButton(name, callback_data=f"{prefix}_{item_id}")])
    return InlineKeyboardMarkup(keyboard)

# ===== SIZE BUTTONS =====
def build_size_buttons(pid):
    cursor.execute("SELECT size, stock FROM sizes WHERE product_id=?", (pid,))
    sizes = cursor.fetchall()

    buttons = []
    for s, st in sizes:
        if st > 0:
            label = f"{s} ({st})"
            callback = f"buy_{pid}_{s}"
        else:
            label = f"{s} (0) ❌"
            callback = "no_stock"

        buttons.append([InlineKeyboardButton(label, callback_data=callback)])

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
            InlineKeyboardButton("➕", callback_data=f"plus_{pid}_{s}")
        ])

    buttons.append([
        InlineKeyboardButton("🗑 Delete Product", callback_data=f"deleteproduct_{pid}")
    ])

    return InlineKeyboardMarkup(buttons)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, "en")

    keyboard = [[KeyboardButton(LANG[lang]["shop"])]]

    if is_allowed(user_id):
        keyboard.append([KeyboardButton(LANG[lang]["manage"])])

    keyboard.append([KeyboardButton("🌐 Language")])

    await update.message.reply_text(
        LANG[lang]["welcome"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ===== BUTTON =====
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = query.from_user.id
    lang = user_lang.get(user_id, "en")

    if data.startswith("cat_"):
        cat_id = data.split("_")[1]

        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
        for pid, file_id, price, _ in cursor.fetchall():

            await query.message.reply_photo(
                photo=file_id,
                caption=f"💲 {price}\n────────────\n{LANG[lang]['select_size']}",
                reply_markup=build_size_buttons(pid)
            )

    elif data.startswith("buy_"):
        _, pid, size = data.split("_")

        cursor.execute("SELECT stock FROM sizes WHERE product_id=? AND size=?", (pid, size))
        result = cursor.fetchone()

        if not result or result[0] <= 0:
            await query.answer(LANG[lang]["out_stock"], show_alert=True)
            return

        cursor.execute("UPDATE sizes SET stock=stock-1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()

        await query.answer(LANG[lang]["order_done"])

        await query.message.edit_reply_markup(reply_markup=build_size_buttons(pid))

    elif data == "no_stock":
        await query.answer(LANG[lang]["out_stock"], show_alert=True)

    elif data.startswith("stockcat_"):
        cat_id = data.split("_")[1]

        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
        for pid, file_id, price, _ in cursor.fetchall():

            await query.message.reply_photo(
                photo=file_id,
                caption=f"📦 {LANG[lang]['stock']}\n💲 {price}",
                reply_markup=build_stock_buttons(pid)
            )

    elif data.startswith("plus_"):
        _, pid, size = data.split("_")
        cursor.execute("UPDATE sizes SET stock=stock+1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        await query.answer("➕")
        await query.message.edit_reply_markup(reply_markup=build_stock_buttons(pid))

    elif data.startswith("minus_"):
        _, pid, size = data.split("_")
        cursor.execute("UPDATE sizes SET stock=stock-1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        await query.answer("➖")
        await query.message.edit_reply_markup(reply_markup=build_stock_buttons(pid))

    elif data.startswith("deleteproduct_"):
        pid = data.split("_")[1]
        cursor.execute("DELETE FROM sizes WHERE product_id=?", (pid,))
        cursor.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        await query.answer("🗑 Deleted")
        await query.message.delete()

    elif data == "no_action":
        await query.answer()

# ===== TEXT =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, "en")

    if text == "🌐 Language":
        keyboard = [
            [KeyboardButton("🇬🇧 English")],
            [KeyboardButton("🇰🇭 Khmer")]
        ]
        await update.message.reply_text("Choose language:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    elif text == "🇬🇧 English":
        user_lang[user_id] = "en"
        await start(update, context)

    elif text == "🇰🇭 Khmer":
        user_lang[user_id] = "kh"
        await start(update, context)

    elif text == LANG[lang]["shop"]:
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text(
            LANG[lang]["choose_category"],
            reply_markup=build_grid(cursor.fetchall(), "cat")
        )

    elif text == LANG[lang]["manage"]:
        keyboard = [
            [KeyboardButton(LANG[lang]["add"])],
            [KeyboardButton(LANG[lang]["stock"])],
            [KeyboardButton(LANG[lang]["back"])]
        ]
        await update.message.reply_text("⚙️ Manage", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    elif text == LANG[lang]["stock"]:
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text(
            f"📦 {LANG[lang]['stock']}",
            reply_markup=build_grid(cursor.fetchall(), "stockcat")
        )

    elif text == LANG[lang]["back"]:
        await start(update, context)

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
