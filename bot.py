import json
import requests
from telegram import Update, Bot, InputFile
from telegram.ext import ContextTypes
from config import TELEGRAM_BOT_TOKEN, PINATA_API_KEY, PINATA_API_SECRET, TELEGRAM_WEBHOOK_URL
from users import create_or_update_user, get_user_by_telegram, init_db as init_users_db
from store import add_product, list_products, init_db as init_store_db
from history import log_action, init_db as init_history_db
from ai import ask_ai
from distribute import distribute_reward
from wallet import get_balance, send_tokens

# initialize DB schemas
init_users_db()
init_store_db()
init_history_db()

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Helper: pin file to Pinata (or replace with other IPFS pinning)
def pin_file_to_pinata(file_bytes, filename):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {
        "pinata_api_key": PINATA_API_KEY,
        "pinata_secret_api_key": PINATA_API_SECRET
    }
    files = {"file": (filename, file_bytes)}
    resp = requests.post(url, files=files, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("IpfsHash")
    else:
        return None

# Handlers used by webhook main
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    create_or_update_user(tg_id)
    await update.message.reply_text("ברוכים הבאים לאקוסיסטם SLH. השתמש ב /help")

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "/start - התחלה\n"
        "/help - עזרה\n"
        "/setwallet <address> - קבע את ארנק ה‑BSC שלך\n"
        "/balance - הראה יתרת SLH בארנק שלך\n"
        "/addproduct <name>,<price> - הוסף מוצר; שלח תמונה לפני הפקודה להוספת תמונה\n"
        "/myproducts - הצג את החנות שלך\n"
        "/buy <product_id> <quantity> <buyer_wallet> - בצע רכישה (ישירות מפתרון תשלום)\n"
        "/ai <שאלה> - שאל את ה‑AI\n    "
    )
    await update.message.reply_text(txt)

async def handle_setwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("שימוש: /setwallet <address>")
        return
    addr = args[0]
    create_or_update_user(update.effective_user.id, wallet_address=addr)
    log_action(update.effective_user.id, "set_wallet", metadata=addr)
    await update.message.reply_text(f"ארנק נשמר: {addr}")

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_telegram(update.effective_user.id)
    if not user or not user.wallet_address:
        await update.message.reply_text("אין ארנק מוגדר. השתמש ב /setwallet <address>")
        return
    bal = get_balance(user.wallet_address)
    if isinstance(bal, dict) and bal.get("error"):
        await update.message.reply_text(f"שגיאה ב־balance: {bal['error']}")
    else:
        await update.message.reply_text(f"יתרתך: {bal} { 'SLH' }")

async def handle_addproduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if "," not in text:
        await update.message.reply_text("שימוש: /addproduct <name>,<price>")
        return
    name, price = text.split(",", 1)
    image_ipfs = None
    # check if last message had photo in context.bot_data
    last_photo = context.chat_data.get("last_photo")
    if last_photo:
        # last_photo expected as bytes
        ipfs_hash = pin_file_to_pinata(last_photo, "product.jpg")
        if ipfs_hash:
            image_ipfs = f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
    p = add_product(update.effective_user.id, name.strip(), float(price.strip()), image_ipfs=image_ipfs)
    log_action(update.effective_user.id, "add_product", metadata=str(p.id))
    await update.message.reply_text(f"נוצר מוצר: {p.id} - {p.name} ב־{p.price_slh} SLH")

async def handle_myproducts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prods = list_products(update.effective_user.id)
    if not prods:
        await update.message.reply_text("אין מוצרים בחנות שלך.")
        return
    for p in prods:
        msg = f"ID: {p.id}\n{p.name}\nPrice: {p.price_slh} SLH\n"
        if p.image_ipfs:
            await update.message.reply_photo(photo=p.image_ipfs, caption=msg)
        else:
            await update.message.reply_text(msg)

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("שלח שאלה אחרי /ai")
        return
    resp = ask_ai(prompt)
    await update.message.reply_text(resp)

async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # buy <product_id> <quantity> <buyer_wallet>
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("שימוש: /buy <product_id> <quantity> <wallet>")
        return
    product_id = int(args[0])
    quantity = int(args[1])
    buyer_wallet = args[2]
    # get product and compute total
    from store import get_product
    p = get_product(product_id)
    if not p:
        await update.message.reply_text("מוצר לא נמצא")
        return
    total = p.price_slh * quantity
    # כאן תוכל ליישם תהליך תשלום מלא מול smart contract / gateway
    await update.message.reply_text(f"צריך לתשלום {total} SLH אל {p.owner_telegram_id}. שלח/י את הטרנסאקציה מכתובתך.")
    log_action(update.effective_user.id, "buy_attempt", metadata=f"{product_id} qty {quantity} wallet {buyer_wallet}")

# photo handler: store last photo bytes in chat_data to be used by /addproduct
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await bot.get_file(photo.file_id)
    b = await file.download_as_bytearray()
    context.chat_data["last_photo"] = bytes(b)
    await update.message.reply_text("תמונה התקבלה. עכשיו שלח /addproduct שם,מחיר כדי להוסיף מוצר עם התמונה.")

# webhook dispatcher adapter for FastAPI (receives Update.json)
def register_handlers(application):
    from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("setwallet", handle_setwallet))
    application.add_handler(CommandHandler("balance", handle_balance))
    application.add_handler(CommandHandler("addproduct", handle_addproduct))
    application.add_handler(CommandHandler("myproducts", handle_myproducts))
    application.add_handler(CommandHandler("ai", handle_ai))
    application.add_handler(CommandHandler("buy", handle_buy))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
