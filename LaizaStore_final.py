from database import init_db

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

import sqlite3
import os


# ===== KHMER TEXT =====
SHOP_BTN = "🛍 ទិញទំនិញ"
MANAGE_BTN = "⚙️ គ្រប់គ្រង"
ADD_BTN = "➕ បន្ថែម"
STOCK_BTN = "📦 ស្តុក"
BACK_BTN = "🔙 ត្រឡប់ក្រោយ"

ADD_PRODUCT_BTN = "➕ ម៉ូតស្បែកជើង"
ADD_CATEGORY_BTN = "➕ បន្ថែមប្រភេទស្បែកជើង"
DELETE_CATEGORY_BTN = "🗑 លុបប្រភេទទំនិញ"
ADD_MORE_CATEGORY_BTN = "➕ បន្ថែមប្រភេទទំនិញទៀត"
CATEGORY_BTN = "📦 ប្រភេទទំនិញ"
ADD_MORE_PRODUCT_BTN = "➕ បន្ថែមម៉ូតស្បែកជើងទៀត"


# ===== DATABASE =====
conn = sqlite3.connect("store.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, file_id TEXT, price TEXT, category_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS sizes (id INTEGER PRIMARY KEY, product_id INTEGER, size TEXT, stock INTEGER)")
conn.commit()


# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")

OWNER_ID = 6178165984
ALLOWED_USERS = [OWNER_ID, 1465920098, 925794809]


def is_allowed(user_id):
    return user_id in ALLOWED_USERS


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
        nav.append(InlineKeyboardButton("⬅️ ថយក្រោយ", callback_data=f"{prefix}_page_{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("➡️ បន្ទាប់", callback_data=f"{prefix}_page_{page+1}"))
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
        if len(row) == 3:
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
            InlineKeyboardButton("🗑", callback_data=f"deletesize_{pid}_{s}"),
        ])
    return InlineKeyboardMarkup(buttons)
    
# ===== TOTAL STOCK =====
def get_total_stock(pid):
    cursor.execute("SELECT SUM(stock) FROM sizes WHERE product_id=?", (pid,))
    total = cursor.fetchone()[0]
    return total if total else 0
    

# ===== FULL STOCK KEYBOARD =====
def build_full_stock_keyboard(pid):
    keyboard = list(build_stock_buttons(pid).inline_keyboard)
    keyboard.append([
        InlineKeyboardButton("➕ ទំហំ", callback_data=f"addsize_{pid}"),
        InlineKeyboardButton("✏️ កែតម្លៃ", callback_data=f"editprice_{pid}"),
        InlineKeyboardButton("🗑 លុបម៉ូតស្បែកជើងនេះ", callback_data=f"deleteproduct_{pid}")
    ])
    return InlineKeyboardMarkup(keyboard)


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_allowed(user_id):
        keyboard = [
            [KeyboardButton(SHOP_BTN)],
            [KeyboardButton(MANAGE_BTN)]
        ]
    else:
        keyboard = [[KeyboardButton(SHOP_BTN)]]
    await update.message.reply_text(
        "✨ ស្វាគមន៍មកកាន់ Laiza Store​ 👠\n\nសូមចុច​​ 🛍 ទិញទំនិញ ដើម្បីមើលម៉ូតស្បែកជើង",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# ===== BUTTON HANDLER =====
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    print("CLICKED:", data)
    

    # ===== PAGINATION =====
    if data.startswith("cat_page_") or data.startswith("stockcat_page_") or data.startswith("addcat_page_"):
        parts = data.split("_")
        prefix = parts[0]
        page = int(parts[-1])
        cursor.execute("SELECT * FROM categories")
        await query.message.edit_reply_markup(
            reply_markup=build_grid(cursor.fetchall(), prefix, page)
        )
        return
        

    # ===== CATEGORY VIEW =====
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
        products = cursor.fetchall()
        if not products:
            await query.answer("⚠️ គ្មានម៉ូតស្បែកជើង", show_alert=False)
            await query.message.reply_text("⚠️ មិនមានម៉ូតស្បែកជើងនៅក្នុងប្រភេទនេះ")
            return
        for pid, file_id, price, _ in products:
            await query.message.reply_photo(
                photo=file_id,
                caption=f"តម្លៃ: {price} ក្នុង1គូ\n────────────\nសូមជ្រើសទំហំ:",
                reply_markup=build_size_buttons(pid)
            )
        return

    
    # ===== BUY =====
    elif data.startswith("buy_"):
        _, pid, size = data.split("_")
        cursor.execute("SELECT stock FROM sizes WHERE product_id=? AND size=?", (pid, size))
        stock = cursor.fetchone()
        if not stock or stock[0] <= 0:
            await query.answer("អស់ស្តុក ❌", show_alert=True)
            return
        cursor.execute("UPDATE sizes SET stock=stock-1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        cursor.execute("SELECT stock FROM sizes WHERE product_id=? AND size=?", (pid, size))
        new_stock = cursor.fetchone()[0]
        cursor.execute("SELECT price FROM products WHERE id=?", (pid,))
        price = cursor.fetchone()[0]
        await query.answer("បានបញ្ជាទិញ ✅")
        await query.message.edit_reply_markup(reply_markup=build_size_buttons(pid))
        await query.message.reply_text(
            f"✅ បានបញ្ជាទិញ!\n\nទំហំ: {size}\nតម្លៃ: {price}\nនៅសល់: {new_stock}"
        )
        return
    elif data == "no_stock":
        await query.answer("អស់ស្តុក ❌", show_alert=True)
        return
        

    # ===== ADD PRODUCT FLOW =====
    elif data.startswith("addcat_"):
        cid = data.split("_")[1]
        context.user_data["category_id"] = cid
        context.user_data["step"] = "photo"
        await query.message.reply_text("📸 ផ្ញើរូបស្បែកជើង")
        return
        

    # ===== CATEGORY MENU =====
    elif data == "add_category_inline":
        context.user_data["step"] = "add_cat"
        await query.message.reply_text("📝 បញ្ចូលឈ្មោះប្រភេទទំនិញថ្មី")
        return

    elif data.startswith("editcat_"):
        cid = data.split("_")[1]
        context.user_data["step"] = "edit_category"
        context.user_data["category_id"] = cid
        await query.message.reply_text("✏️ បញ្ចូលឈ្មោះប្រភេទថ្មី")
        return

    elif data.startswith("delcat_"):
        cid = data.split("_")[1]
        cursor.execute("DELETE FROM categories WHERE id=?", (cid,))
        cursor.execute("DELETE FROM products WHERE category_id=?", (cid,))
        conn.commit()
        await query.message.reply_text("🗑 បានលុបប្រភេទទំនិញរួចរាល់")
        return
        

    # ===== STOCK VIEW =====
    elif data.startswith("stockcat_"):
        cid = data.split("_")[1]
        cursor.execute("SELECT * FROM products WHERE category_id=?", (cid,))
        products = cursor.fetchall()
        if not products:
            await query.answer("❌ គ្មានម៉ូតស្បែកជើងក្នុងប្រភេទទំនិញនេះ", show_alert=True)
            return
        for pid, file_id, price, _ in products:
            keyboard = list(build_stock_buttons(pid).inline_keyboard)
            keyboard.append([
                InlineKeyboardButton("➕ ទំហំ", callback_data=f"addsize_{pid}"),
                InlineKeyboardButton("✏️ កែតម្លៃ", callback_data=f"editprice_{pid}"),
                InlineKeyboardButton("🗑 លុបម៉ូតស្បែកជើងនេះ", callback_data=f"deleteproduct_{pid}")
            ])
            total = get_total_stock(pid)
            await query.message.reply_photo(
                photo=file_id,
                caption=f"📦 ព័ត៌មានម៉ូតស្បែកជើងនេះ\n────────────\n💰 តម្លៃ: {price}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
        

    # ===== STOCK CONTROL =====
    elif data.startswith("plus_"):
        _, pid, size = data.split("_")
        cursor.execute("UPDATE sizes SET stock=stock+1 WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        cursor.execute("SELECT file_id, price FROM products WHERE id=?", (pid,))
        file_id, price = cursor.fetchone()
        total = get_total_stock(pid)
        await query.message.edit_caption(
            caption=f"📦 ព័ត៌មានម៉ូតស្បែកជើងនេះ\n────────────\n💰 តម្លៃ: {price}\n📦 ស្តុកសរុប: {total}",
            reply_markup=build_full_stock_keyboard(pid))
        
    elif data.startswith("minus_"):
        _, pid, size = data.split("_")
        cursor.execute("UPDATE sizes SET stock=MAX(stock-1,0) WHERE product_id=? AND size=?", (pid, size))
        conn.commit()
        cursor.execute("SELECT file_id, price FROM products WHERE id=?", (pid,))
        file_id, price = cursor.fetchone()
        total = get_total_stock(pid)
        await query.message.edit_caption(
            caption=f"📦 ព័ត៌មានម៉ូតស្បែកជើងនេះ\n────────────\n💰 តម្លៃ: {price}\n📦 ស្តុកសរុប: {total}",
            reply_markup=build_full_stock_keyboard(pid))
        
    elif data.startswith("addsize_"):
        pid = data.split("_")[1]
        context.user_data["step"] = "add_size"
        context.user_data["product_id"] = pid
        await query.message.reply_text("📏 បញ្ចូលទំហំស្បែកជើង និងចំនួន\nឧទាហរណ៍: 42:5")
        return
        

    elif data.startswith("deletesize_"):
        _, pid, size = data.split("_")
        cursor.execute(
            "DELETE FROM sizes WHERE product_id=? AND size=?",
            (pid, size)
        )
        conn.commit()
        cursor.execute("SELECT file_id, price FROM products WHERE id=?", (pid,))
        file_id, price = cursor.fetchone()
        keyboard = list(build_stock_buttons(pid).inline_keyboard)
        keyboard.append([
            InlineKeyboardButton("➕ ទំហំ", callback_data=f"addsize_{pid}"),
            InlineKeyboardButton("✏️ កែតម្លៃ", callback_data=f"editprice_{pid}"),
            InlineKeyboardButton("🗑 លុបម៉ូតស្បែកជើងនេះ", callback_data=f"deleteproduct_{pid}")
        ])
        await query.message.delete()
        await query.message.reply_photo(
            photo=file_id,
            caption=f"📦 ព័ត៌មានម៉ូតស្បែកជើងនេះ\n────────────\n💰 តម្លៃ: {price}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        

    elif data.startswith("deleteproduct_"):
        pid = data.split("_")[1]
        keyboard = [
            [
                InlineKeyboardButton("✅ បាទ/ចាស លុប", callback_data=f"confirmdelete_{pid}"),
                InlineKeyboardButton("❌ បោះបង់", callback_data="canceldelete")
            ]
        ]
        await query.message.reply_text(
            "⚠️ តើអ្នកប្រាកដថាចង់លុបមែនទេ?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        

    elif data.startswith("confirmdelete_"):
        pid = data.split("_")[1]
        cursor.execute("DELETE FROM sizes WHERE product_id=?", (pid,))
        cursor.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        await query.message.reply_text("🗑 បានលុបរួចរាល់")
        return


    elif data == "canceldelete":
        await query.message.reply_text("❌ បានបោះបង់")
        return

    
    elif data.startswith("editprice_"):
        pid = data.split("_")[1]
        context.user_data["step"] = "edit_price"
        context.user_data["product_id"] = pid
        await query.message.reply_text("បញ្ចូលតម្លៃថ្មី:")
        return

# ===== TEXT =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    step = context.user_data.get("step")
    print("TEXT CLICKED:", text)
    

    # ===== BLOCK NORMAL USERS =====
    if not is_allowed(user_id):
        if text != SHOP_BTN:
            await update.message.reply_text("🚫 អ្នកអាចប្រើបានតែ ទិញទំនិញ")
            return
            

    # ===== STEP FLOW =====
    if step == "add_cat":
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (text,))
        conn.commit()
        context.user_data.clear()

        keyboard = [
            [KeyboardButton(ADD_MORE_CATEGORY_BTN)],
            [KeyboardButton(BACK_BTN)]
        ]
        await update.message.reply_text(
            "✅ បានបន្ថែមប្រភេទទំនិញថ្មីរួចរាល់\n────────────\nតើចង់បន្ថែមទៀតទេ? 🐶",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
        
    elif step == "price":
        context.user_data["price"] = text
        context.user_data["step"] = "sizes"
        await update.message.reply_text("📏 បញ្ចូលទំហំស្បែកជើង និងចំនួន\n(ឧទាហរណ៍ 36:0,37:0,38:0,39:0,40:0)")
        return

    elif step == "sizes":
        cursor.execute(
            "INSERT INTO products (file_id, price, category_id) VALUES (?,?,?)",
            (context.user_data["file_id"], context.user_data["price"], context.user_data["category_id"])
        )
        pid = cursor.lastrowid
        for item in text.split(","):
            if ":" not in item:
                continue
            s, st = item.split(":")
            cursor.execute(
                "INSERT INTO sizes (product_id, size, stock) VALUES (?,?,?)",
                (pid, s, int(st))
            )
        conn.commit()
        context.user_data.clear()
        keyboard = [
            [KeyboardButton(ADD_MORE_PRODUCT_BTN)],
            [KeyboardButton(BACK_BTN)]
        ]
        await update.message.reply_text(
            "✅ បានបញ្ចូលម៉ូតស្បែកជើង\n────────────\nតើចង់បន្ថែមទៀតទេ? 🐶",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    elif step == "add_size":
        try:
            size, stock = text.split(":")
            pid = context.user_data["product_id"]
            cursor.execute(
                "INSERT INTO sizes (product_id, size, stock) VALUES (?,?,?)",
                (pid, size, int(stock))
            )
            conn.commit()
            cursor.execute("SELECT file_id, price FROM products WHERE id=?", (pid,))
            file_id, price = cursor.fetchone()
            context.user_data.clear()
            keyboard = list(build_stock_buttons(pid).inline_keyboard)
            keyboard.append([
                InlineKeyboardButton("➕ ទំហំ", callback_data=f"addsize_{pid}"),
                InlineKeyboardButton("✏️ កែតម្លៃ", callback_data=f"editprice_{pid}"),
                InlineKeyboardButton("🗑 លុបម៉ូតស្បែកជើងនេះ", callback_data=f"deleteproduct_{pid}")
            ])
            total = get_total_stock(pid)
            await update.message.reply_photo(
                photo=file_id,
                caption=f"📦 ព័ត៌មានម៉ូតស្បែកជើងនេះ\n────────────\n💰 តម្លៃ: {price}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ format: 42:5")
        return
        

    # ===== MAIN MENU =====
    elif text == SHOP_BTN:
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text(
            "ជ្រើសរើសប្រភេទស្បែកជើងជាមុនសិន",
            reply_markup=build_grid(cursor.fetchall(), "cat")
        )

    elif text == MANAGE_BTN:
        keyboard = [
            [KeyboardButton(ADD_BTN)],
            [KeyboardButton(STOCK_BTN)],
            [KeyboardButton(BACK_BTN)]
        ]
        await update.message.reply_text(
            "⚙️ ការគ្រប់គ្រងផ្សេង",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == ADD_BTN:
        keyboard = [
            [KeyboardButton(ADD_PRODUCT_BTN)],
            [KeyboardButton("📦 ប្រភេទស្បែកជើង")],
            [KeyboardButton(BACK_BTN)]
        ]
        await update.message.reply_text(
            "តើអ្នកចង់បន្ថែមអ្វី?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    elif text == "📦 ប្រភេទស្បែកជើង":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        if not cats:
            msg = "❌ មិនទាន់មានប្រភេទស្បែកជើងនៅឡើយទេ\n👉 សូមបន្ថែមប្រភេទថ្មី"
            keyboard_inline = []
        else:
            msg = "📦​ ការគ្រប់គ្រងប្រភេទស្បែកជើង"
            keyboard_inline = []
            for cid, name in cats:
                keyboard_inline.append([
                    InlineKeyboardButton(f"{name}", callback_data=f"viewcat_{cid}")
                ])
                keyboard_inline.append([
                    InlineKeyboardButton("✏️ កែ", callback_data=f"editcat_{cid}"),
                    InlineKeyboardButton("🗑 លុប", callback_data=f"delcat_{cid}")
                ])
                keyboard_inline.append([
                    InlineKeyboardButton("────────────", callback_data="no_action")
                ])

        # ✅ REPLY KEYBOARD (BOTTOM)
        reply_keyboard = [
            [KeyboardButton(ADD_CATEGORY_BTN)],
            [KeyboardButton(BACK_BTN)]
        ]
        await update.message.reply_text(
            msg,
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        )
        # ✅ SEND INLINE CATEGORY LIST (SECOND MESSAGE)
        if keyboard_inline:
            await update.message.reply_text(
                f"📦 ប្រភេទស្បែកជើងសរុប: {len(cats)}\n────────────\n👇 ជ្រើសរើសប្រភេទស្បែកជើង",
                reply_markup=InlineKeyboardMarkup(keyboard_inline)
            )
            
    elif text == ADD_CATEGORY_BTN:
        context.user_data["step"] = "add_cat"
        await update.message.reply_text("📝 បញ្ចូលឈ្មោះប្រភេទស្បែកជើងថ្មី")

    
    elif step == "edit_category":
        cid = context.user_data["category_id"]
        cursor.execute("UPDATE categories SET name=? WHERE id=?", (text, cid))
        conn.commit()
        context.user_data.clear()
        await update.message.reply_text("✅ បានកែឈ្មោះប្រភេទស្បែកជើង")
        return

    elif text == ADD_MORE_CATEGORY_BTN:
        context.user_data["step"] = "add_cat"
        await update.message.reply_text("📝 បញ្ចូលឈ្មោះប្រភេទស្បែកជើងថ្មី")

    elif text == ADD_PRODUCT_BTN:
        cursor.execute("SELECT * FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await update.message.reply_text("❌ សូមបន្ថែមប្រភេទស្បែកជើងមុន")
            return
        await update.message.reply_text(
            "ជ្រើសរើសប្រភេទស្បែកជើងជាមុនសិន",
            reply_markup=build_grid(cats, "addcat")
        )

    elif text == ADD_MORE_PRODUCT_BTN:
        cursor.execute("SELECT * FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await update.message.reply_text("❌ សូមបន្ថែមប្រភេទស្បែកជើងមុន")
            return
        await update.message.reply_text(
            "ជ្រើសរើសប្រភេទស្បែកជើងជាមុនសិន",
            reply_markup=build_grid(cats, "addcat")
        )

    elif text == STOCK_BTN:
        cursor.execute("SELECT * FROM categories")
        await update.message.reply_text(
            "📦 ស្តុក:",
            reply_markup=build_grid(cursor.fetchall(), "stockcat")
        )

    elif text == BACK_BTN:
        await start(update, context)

    elif step == "edit_price":
        pid = context.user_data["product_id"]
        cursor.execute(
            "UPDATE products SET price=? WHERE id=?",
            (text, pid)
        )
        conn.commit()
        context.user_data.clear()
        await update.message.reply_text("✅ បានកែតម្លៃរួច")
        return
        

# ===== PHOTO =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "photo":
        return

    context.user_data["file_id"] = update.message.photo[-1].file_id
    context.user_data["step"] = "price"
    await update.message.reply_text("សូមផ្ញើតម្លៃ")


# ===== RUN =====
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_click))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()
