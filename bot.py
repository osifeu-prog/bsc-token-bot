import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from wallet import get_balance, send_tokens
from ai import ask_ai
from store import add_product, get_store
from users import register_user, set_wallet, get_user
from history import log_action

BOT_APP = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    await update.message.reply_text("ברוך הבא לאקוסיסטם של Sela ללא גבולות 🌐\nהשתמש ב/commands לקבלת פונקציות.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = "/start\n/balance\n/setwallet <address>\n/add <name>,<price>\n/store\n/ai <שאלה>\n/send <address> <amount>"
    await update.message.reply_text(txt)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    addr = u.get("wallet") if u else None
    if not addr:
        await update.message.reply_text("אין ארנק מוגדר. הגדר באמצעות /setwallet <address>")
        return
    bal = await get_balance(addr)
    await update.message.reply_text(f"היתרה של {addr} : {bal} { 'SLH' }")

async def setwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        addr = context.args[0]
        set_wallet(update.effective_user.id, addr)
        await update.message.reply_text(f"ארנק נשמר: {addr}")
    except Exception:
        await update.message.reply_text("שימוש: /setwallet <address>")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        full = " ".join(context.args)
        name, price = full.split(",", 1)
        add_product(update.effective_user.id, {"name": name.strip(), "price": price.strip()})
        log_action(update.effective_user.id, f"added product {name.strip()} price {price.strip()}")
        await update.message.reply_text(f"המוצר \"{name.strip()}\" נוסף בחנות שלך.")
    except Exception:
        await update.message.reply_text("שימוש: /add שם מוצר,מחיר")

async def store_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_store(update.effective_user.id)
    if not s:
        await update.message.reply_text("אין מוצרים בחנות שלך.")
        return
    for p in s:
        await update.message.reply_text(f"🛍️ {p['name']} - {p['price']} SLH")

async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("תן שאלה אחרי /ai")
        return
    resp = await ask_ai(prompt)
    await update.message.reply_text(resp)

async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        to = context.args[0]
        amount = context.args[1]
        tx = await send_tokens(to, int(amount))
        log_action(update.effective_user.id, f"sent {amount} to {to} tx:{tx}")
        await update.message.reply_text(f"הפעולה נשלחה: {tx}")
    except Exception as e:
        await update.message.reply_text(f"שגיאה בשליחה: {str(e)}")

def build_app(token):
    global BOT_APP
    BOT_APP = ApplicationBuilder().token(token).build()
    BOT_APP.add_handler(CommandHandler("start", start))
    BOT_APP.add_handler(CommandHandler("help", help_cmd))
    BOT_APP.add_handler(CommandHandler("balance", balance))
    BOT_APP.add_handler(CommandHandler("setwallet", setwallet))
    BOT_APP.add_handler(CommandHandler("add", add))
    BOT_APP.add_handler(CommandHandler("store", store_cmd))
    BOT_APP.add_handler(CommandHandler("ai", ai_cmd))
    BOT_APP.add_handler(CommandHandler("send", send_cmd))
    return BOT_APP

async def run_polling(token):
    app = build_app(token)
    await app.run_polling()
