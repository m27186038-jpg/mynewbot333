import logging
import re
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─── تنظیمات ───────────────────────────────────────────
TOKEN     = "8926646209:AAF8ZjUYWDPGsapeaBIyAL8n9anUCJ8hH0k"
ADMIN_ID  = 7969786815
CARD_NUM  = "6219-8614-5512-3868"
CARD_NAME = "هاشمی"

PLANS = {
    "p1": ("10 گیگ",  150_000),
    "p2": ("20 گیگ",  300_000),
    "p3": ("30 گیگ",  450_000),
    "p4": ("40 گیگ",  600_000),
    "p5": ("500 گیگ", 750_000),
}

WAIT_RECEIPT = 1

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

# ─── دیتابیس ───────────────────────────────────────────
DB = os.path.join(os.path.dirname(__file__), "data.db")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                name TEXT,
                joined TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orders(
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                uid      INTEGER,
                plan_id  TEXT,
                label    TEXT,
                price    INTEGER,
                status   TEXT DEFAULT 'pending',
                file_id  TEXT,
                created  TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

def add_user(uid, name):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO users(id,name) VALUES(?,?)", (uid, name))

def new_order(uid, pid, label, price):
    with db() as c:
        cur = c.execute("INSERT INTO orders(uid,plan_id,label,price) VALUES(?,?,?,?)",
                        (uid, pid, label, price))
        return cur.lastrowid

def set_file(oid, fid):
    with db() as c:
        c.execute("UPDATE orders SET file_id=? WHERE id=?", (fid, oid))

def get_order(oid):
    with db() as c:
        r = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        return dict(r) if r else None

def set_status(oid, st):
    with db() as c:
        c.execute("UPDATE orders SET status=? WHERE id=?", (st, oid))

def user_orders(uid):
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM orders WHERE uid=? ORDER BY id DESC LIMIT 10", (uid,))]

def all_orders():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM orders ORDER BY id DESC")]

def all_users():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM users")]

# ─── کیبورد اصلی ───────────────────────────────────────
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 خرید کانفیگ",   callback_data="buy")],
        [InlineKeyboardButton("📦 سفارش‌های من",  callback_data="orders")],
        [InlineKeyboardButton("📞 پشتیبانی",      callback_data="support")],
    ])

# ─── /start ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    add_user(u.id, u.first_name)
    txt = f"👋 سلام {u.first_name}!\n\n🔐 به ربات فروش کانفیگ V2Ray خوش اومدی.\n\nاز منو انتخاب کن 👇"
    if update.message:
        await update.message.reply_text(txt, reply_markup=main_kb())
    else:
        await update.callback_query.edit_message_text(txt, reply_markup=main_kb())

# ─── منوی خرید ─────────────────────────────────────────
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = []
    for pid, (label, price) in PLANS.items():
        emoji = "🚀" if "500" in label else "📦"
        rows.append([InlineKeyboardButton(
            f"{emoji} {label}  |  {price:,} تومان",
            callback_data=f"pl_{pid}"
        )])
    rows.append([InlineKeyboardButton("🔙 برگشت", callback_data="home")])
    await q.edit_message_text("📋 *پلن موردنظرت رو انتخاب کن:*",
                              reply_markup=InlineKeyboardMarkup(rows),
                              parse_mode="Markdown")

# ─── انتخاب پلن ─────────────────────────────────────────
async def pick_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = q.data.replace("pl_", "")
    label, price = PLANS[pid]
    context.user_data["pid"]   = pid
    context.user_data["label"] = label
    context.user_data["price"] = price
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ پرداخت کردم، رسید میفرستم", callback_data="receipt")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="buy")],
    ])
    await q.edit_message_text(
        f"💳 *اطلاعات پرداخت*\n\n"
        f"📦 پلن: *{label}*\n"
        f"💰 مبلغ: *{price:,} تومان*\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏦 شماره کارت:\n`{CARD_NUM}`\n\n"
        f"👤 به نام: *{CARD_NAME}*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ بعد از واریز، دکمه زیر رو بزن و رسید رو بفرست.",
        reply_markup=kb, parse_mode="Markdown"
    )

# ─── درخواست رسید ───────────────────────────────────────
async def ask_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not context.user_data.get("pid"):
        await q.answer("اول یه پلن انتخاب کن!", show_alert=True)
        return ConversationHandler.END
    await q.edit_message_text(
        "📸 *تصویر رسید پرداخت رو بفرست* 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ انصراف", callback_data="home")
        ]])
    )
    return WAIT_RECEIPT

# ─── دریافت رسید ────────────────────────────────────────
async def got_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u  = update.effective_user
    ud = context.user_data
    pid, label, price = ud.get("pid"), ud.get("label"), ud.get("price")

    if not pid:
        await update.message.reply_text("❌ مشکل پیش اومد. دوباره /start بزن.")
        return ConversationHandler.END

    msg = update.message
    if msg.photo:
        fid, ftype = msg.photo[-1].file_id, "photo"
    elif msg.document:
        fid, ftype = msg.document.file_id, "doc"
    else:
        await msg.reply_text("⚠️ لطفاً فقط عکس رسید رو بفرست.")
        return WAIT_RECEIPT

    oid = new_order(u.id, pid, label, price)
    set_file(oid, fid)

    await msg.reply_text(
        f"✅ *رسید دریافت شد!*\n\n"
        f"🔢 شماره سفارش: `#{oid}`\n"
        f"⏳ ادمین بررسی میکنه و کانفیگ برات میاد 🚀",
        parse_mode="Markdown"
    )

    # ─ ارسال به ادمین ─
    cap = (
        f"🔔 *سفارش جدید!*\n\n"
        f"🔢 سفارش: `#{oid}`\n"
        f"👤 [{u.first_name}](tg://user?id={u.id})  |  `{u.id}`\n"
        f"📦 پلن: *{label}*\n"
        f"💰 مبلغ: *{price:,} تومان*"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ تأیید", callback_data=f"ok_{oid}"),
        InlineKeyboardButton("❌ رد",   callback_data=f"no_{oid}"),
    ]])
    try:
        fn = context.bot.send_photo if ftype == "photo" else context.bot.send_document
        kw = {"photo": fid} if ftype == "photo" else {"document": fid}
        await fn(ADMIN_ID, **kw, caption=cap, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"ارسال به ادمین: {e}")

    return ConversationHandler.END

# ─── تأیید (ادمین) ──────────────────────────────────────
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("❌ دسترسی ندارید!", show_alert=True); return
    await q.answer()

    oid = int(q.data.split("_")[1])
    o   = get_order(oid)
    if not o or o["status"] != "pending":
        await q.answer("قبلاً پردازش شده!", show_alert=True); return

    set_status(oid, "approved")
    try:
        await context.bot.send_message(
            o["uid"],
            f"✅ *پرداخت تأیید شد!*\n📦 پلن: *{o['label']}*\n⏳ کانفیگ به زودی ارسال میشه...",
            parse_mode="Markdown"
        )
    except: pass

    await q.edit_message_caption(
        caption=(q.message.caption or "") +
                f"\n\n✅ *تأیید شد*\n\n📤 کانفیگ رو *ریپلای* کن روی این پیام:",
        parse_mode="Markdown", reply_markup=None
    )

# ─── رد (ادمین) ─────────────────────────────────────────
async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("❌ دسترسی ندارید!", show_alert=True); return
    await q.answer()

    oid = int(q.data.split("_")[1])
    o   = get_order(oid)
    if not o or o["status"] != "pending":
        await q.answer("قبلاً پردازش شده!", show_alert=True); return

    set_status(oid, "rejected")
    try:
        await context.bot.send_message(
            o["uid"],
            "❌ *رسید شما تأیید نشد.*\nبرای پیگیری با پشتیبانی در تماس باش.",
            parse_mode="Markdown"
        )
    except: pass

    await q.edit_message_caption(
        caption=(q.message.caption or "") + "\n\n❌ *رد شد*",
        parse_mode="Markdown", reply_markup=None
    )

# ─── ارسال کانفیگ با ریپلای ─────────────────────────────
async def send_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg = update.message
    if not msg.reply_to_message: return

    cap   = msg.reply_to_message.caption or ""
    match = re.search(r"#(\d+)", cap)
    if not match: return

    oid = int(match.group(1))
    o   = get_order(oid)
    if not o or o["status"] not in ("approved", "pending"):
        await msg.reply_text("❌ سفارش معتبر نیست."); return

    header = f"🎉 *کانفیگت آماده‌ست!*\n📦 پلن: *{o['label']}*\n━━━━━━━━━━━━━━━━━━\n"
    try:
        if msg.text:
            await context.bot.send_message(o["uid"], header + f"`{msg.text}`", parse_mode="Markdown")
        elif msg.document:
            await context.bot.send_document(o["uid"], msg.document.file_id, caption=header, parse_mode="Markdown")
        elif msg.photo:
            await context.bot.send_photo(o["uid"], msg.photo[-1].file_id, caption=header, parse_mode="Markdown")
        else:
            await msg.reply_text("❌ فقط متن یا فایل بفرست."); return

        set_status(oid, "delivered")
        await msg.reply_text(f"✅ کانفیگ سفارش #{oid} ارسال شد!")
    except Exception as e:
        await msg.reply_text(f"❌ خطا: {e}")

# ─── سفارش‌های من ───────────────────────────────────────
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    orders = user_orders(q.from_user.id)
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="home")]])
    if not orders:
        await q.edit_message_text("📭 هنوز سفارشی نداری!", reply_markup=back); return

    icons = {"pending":"⏳","approved":"✅","rejected":"❌","delivered":"📬"}
    words = {"pending":"در انتظار","approved":"تأیید شده","rejected":"رد شده","delivered":"تحویل داده شده"}
    txt = "📦 *سفارش‌های شما:*\n\n"
    for o in orders:
        ic = icons.get(o["status"],"❓")
        lb = words.get(o["status"], o["status"])
        txt += f"{ic} `#{o['id']}` ← {o['label']} ← {lb}\n"
    await q.edit_message_text(txt, reply_markup=back, parse_mode="Markdown")

# ─── پشتیبانی ───────────────────────────────────────────
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="home")]])
    await q.edit_message_text(
        "📞 *پشتیبانی*\n\nبرای ارتباط با ادمین پیام بده.\n⏰ پاسخگویی: همه روزه",
        reply_markup=back, parse_mode="Markdown"
    )

# ─── /admin ─────────────────────────────────────────────
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    orders = all_orders()
    users  = all_users()
    income = sum(o["price"] for o in orders if o["status"] in ("approved","delivered"))
    st = {k: sum(1 for o in orders if o["status"]==k) for k in ("pending","approved","delivered","rejected")}

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ در انتظار",    callback_data="adm_p")],
        [InlineKeyboardButton("📊 آمار فروش",   callback_data="adm_s")],
        [InlineKeyboardButton("👥 کاربران",      callback_data="adm_u")],
    ])
    await update.message.reply_text(
        f"🔧 *پنل مدیریت*\n\n"
        f"⏳ در انتظار: *{st['pending']}*\n"
        f"✅ تأیید شده: *{st['approved']}*\n"
        f"📬 تحویل داده شده: *{st['delivered']}*\n"
        f"❌ رد شده: *{st['rejected']}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 کاربران: *{len(users)}*\n"
        f"💰 درآمد: *{income:,} تومان*",
        reply_markup=kb, parse_mode="Markdown"
    )

async def adm_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    rows = [o for o in all_orders() if o["status"] == "pending"]
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="adm_back")]])
    if not rows:
        await q.edit_message_text("✅ سفارش در انتظاری نیست!", reply_markup=back); return
    txt = "⏳ *در انتظار تأیید:*\n\n"
    for o in rows:
        txt += f"🔢 `#{o['id']}` | {o['label']} | `{o['uid']}`\n"
    await q.edit_message_text(txt, reply_markup=back, parse_mode="Markdown")

async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    orders = all_orders()
    income = sum(o["price"] for o in orders if o["status"] in ("approved","delivered"))
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="adm_back")]])
    txt = f"📊 *آمار فروش*\n\n💰 درآمد کل: *{income:,} تومان*\n\n"
    for pid, (label, price) in PLANS.items():
        cnt = sum(1 for o in orders if o["plan_id"]==pid and o["status"] in ("approved","delivered"))
        txt += f"📦 {label}: *{cnt} فروش*  |  {cnt*price:,} ت\n"
    await q.edit_message_text(txt, reply_markup=back, parse_mode="Markdown")

async def adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_ID: return
    users = all_users()
    back = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 برگشت", callback_data="adm_back")]])
    txt = f"👥 *کاربران ({len(users)} نفر):*\n\n"
    for u in users[-25:]:
        txt += f"🆔 `{u['id']}` | {u['name']}\n"
    await q.edit_message_text(txt, reply_markup=back, parse_mode="Markdown")

async def adm_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🔧 پنل ادمین — از /admin استفاده کن.")

# ─── MAIN ───────────────────────────────────────────────
def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_receipt, pattern="^receipt$")],
        states={WAIT_RECEIPT: [MessageHandler(filters.PHOTO | filters.Document.ALL, got_receipt)]},
        fallbacks=[CommandHandler("start", start),
                   CallbackQueryHandler(buy, pattern="^buy$"),
                   CallbackQueryHandler(start, pattern="^home$")],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(conv)

    app.add_handler(CallbackQueryHandler(start,      pattern="^home$"))
    app.add_handler(CallbackQueryHandler(buy,        pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(pick_plan,  pattern="^pl_"))
    app.add_handler(CallbackQueryHandler(my_orders,  pattern="^orders$"))
    app.add_handler(CallbackQueryHandler(support,    pattern="^support$"))
    app.add_handler(CallbackQueryHandler(approve,    pattern="^ok_"))
    app.add_handler(CallbackQueryHandler(reject,     pattern="^no_"))
    app.add_handler(CallbackQueryHandler(adm_pending,pattern="^adm_p$"))
    app.add_handler(CallbackQueryHandler(adm_stats,  pattern="^adm_s$"))
    app.add_handler(CallbackQueryHandler(adm_users,  pattern="^adm_u$"))
    app.add_handler(CallbackQueryHandler(adm_back,   pattern="^adm_back$"))

    app.add_handler(MessageHandler(
        filters.User(ADMIN_ID) & filters.REPLY &
        (filters.TEXT | filters.Document.ALL | filters.PHOTO),
        send_config
    ))

    logging.info("ربات روشن شد ✅")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
