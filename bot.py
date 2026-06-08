user?id={u.id})  |  `{u.id}`\n"
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
