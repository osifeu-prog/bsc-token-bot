from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from wallet import get_balance
from ai import ask_ai
from store import get_store, add_product

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ברוך הבא לאקוסיסטם של Sela ללא גבולות 🌐")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    balance = await get_balance(user)
    await update.message.reply_text(f"היתרה שלך: {balance} SLH")

async def store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store = get_store(update.effective_user.id)
    if not store:
        await update.message.reply_text("אין מוצרים בחנות שלך.")
    else:
        for p in store:
            await update.message.reply_text(f"🛍️ {p['name']} - {p['price']} SLH")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name, price = " ".join(context.args).split(",")
        add_product(update.effective_user.id, {"name": name.strip(), "price": price.strip()})
        await update.message.reply_text(f"המוצר {name} נוסף לחנות שלך.")
    except:
        await update.message.reply_text("שימוש: /add שם מוצר, מחיר")

async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    response = await ask_ai(prompt)
    await update.message.reply_text(response)

def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("balance", balance),
        CommandHandler("store", store),
        CommandHandler("add", add),
        CommandHandler("ai", ai),
    ]
