import os
import logging
import json
import requests
import openai
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telegram
from telegram.ext import Dispatcher, MessageHandler, Filters, CommandHandler, CallbackQueryHandler, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from web3 import Web3

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')
PORT = int(os.getenv('PORT', 10000))

# Blockchain Configuration
SLH_TOKEN_ADDRESS = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
BSC_RPC_URL = "https://bsc-dataseed.binance.org/"
SLH_VALUE_ILS = 444

# Community Links
TELEGRAM_GROUP_URL = "https://t.me/+HIzvM8sEgh1kNWY0"
TELEGRAM_GROUP_ID = -1002981609404

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in environment variables")

# Initialize AI
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = telegram.Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# ==================== SIMPLIFIED VERSION FOR PRODUCTION ====================

class NotificationManager:
    def __init__(self):
        self.price_alerts = {}
    
    def should_notify_balance_change(self, user_id, old_balance, new_balance):
        threshold = 10
        return abs(new_balance - old_balance) >= threshold

notification_manager = NotificationManager()

class AdvancedWalletFeatures:
    def __init__(self, rpc_url, token_address):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.token_address = token_address
        self.token_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
        self.token_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=self.token_abi
        )
    
    def get_balance(self, wallet_address):
        try:
            balance = self.token_contract.functions.balanceOf(
                Web3.to_checksum_address(wallet_address)
            ).call()
            decimals = self.token_contract.functions.decimals().call()
            return balance / (10 ** decimals)
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0

advanced_wallet = AdvancedWalletFeatures(BSC_RPC_URL, SLH_TOKEN_ADDRESS)

class UserDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('slh_platform.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                wallet_address TEXT,
                phone TEXT,
                website TEXT,
                materials TEXT,
                total_gifts_sent REAL DEFAULT 0,
                total_gifts_received REAL DEFAULT 0,
                joined_group BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                to_user_id INTEGER,
                amount REAL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users (user_id),
                FOREIGN KEY (to_user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        self.conn.commit()
    
    def update_wallet(self, user_id, wallet_address):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET wallet_address = ? WHERE user_id = ?
        ''', (wallet_address, user_id))
        self.conn.commit()
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    def mark_joined_group(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET joined_group = TRUE WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()

db = UserDatabase()

class AIAssistant:
    def __init__(self):
        self.openai_key = OPENAI_API_KEY
    
    def chat_gpt_response(self, message, context=""):
        if not self.openai_key:
            return "🤖 מצטער, שירות AI לא זמין כרגע."
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"אתה עוזר AI לפלטפורמת SLH. דבר בעברית. {context}"},
                    {"role": "user", "content": message}
                ],
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI Error: {e}")
            return "🤖 מצטער, אירעה שגיאה ב-AI. נסה שוב מאוחר יותר."

ai_assistant = AIAssistant()

# ==================== KEYBOARDS ====================
def get_main_keyboard():
    keyboard = [
        ["👛 הארנק שלי", "🎁 שלח מתנה"],
        ["🤖 עוזר AI", "👥 הצטרף לקהילה"],
        ["📊 סטטיסטיקות", "⚙️ הגדרות"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_ai_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 עזרה בכתיבת חוזה", callback_data="ai_contract_help")],
        [InlineKeyboardButton("💡 ייעוץ השקעות", callback_data="ai_investment_advice")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_community_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 הצטרף לקהילה", url=TELEGRAM_GROUP_URL)],
        [InlineKeyboardButton("✅ אישור הצטרפות", callback_data="confirm_join")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== BOT HANDLERS ====================
def start(update, context):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""
👋 **ברוך הבא {user.first_name}!**

**SLH Platform** - הפלטפורמה למסחר במטבע SLH

💎 **מטבע SLH:** ערך נוכחי {SLH_VALUE_ILS} ₪
🤖 **עוזר AI:** זמין לסיוע
👥 **קהילה:** מאות סוחרים פעילים

**🚀 מה תוכל לעשות:**
• 👛 ניהול ארנק SLH
• 🎁 שליחת מתנות בקהילה  
• 🤖 סיוע AI מתקדם
• 👥 מסחר בקהילה פעילה

**👥 הצטרף לקהילה שלנו:**
{TELEGRAM_GROUP_URL}

בחר אחת האפשרויות למטה 👇
    """
    
    update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

def handle_message(update, context):
    text = update.message.text
    user = update.effective_user
    
    if text == "👛 הארנק שלי":
        my_wallet(update, context)
    elif text == "🎁 שלח מתנה":
        send_gift_menu(update, context)
    elif text == "🤖 עוזר AI":
        ai_assistant_menu(update, context)
    elif text == "👥 הצטרף לקהילה":
        community_join(update, context)
    elif text == "📊 סטטיסטיקות":
        user_stats(update, context)
    elif text == "⚙️ הגדרות":
        update.message.reply_text("⚙️ הגדרות - *בפיתוח*", parse_mode='Markdown')
    elif text.startswith("0x") and len(text) == 42:
        save_wallet_address(update, context, text)
    elif text.startswith("/ai"):
        handle_ai_chat(update, context)
    else:
        update.message.reply_text("אשמח לעזור לך! בחר אחת האפשרויות מהתפריט 📱", reply_markup=get_main_keyboard())

def my_wallet(update, context):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user_data and user_data[4]:
        wallet_address = user_data[4]
        current_balance = advanced_wallet.get_balance(wallet_address)
        
        wallet_text = f"""
**👛 הארנק שלך**

**כתובת ארנק:** 
`{wallet_address}`

**💰 יתרת SLH:** {current_balance:,.2f} SLH
**💎 שווי נוכחי:** {current_balance * SLH_VALUE_ILS:,.0f} ₪

**📊 סטטיסטיקות:**
🎁 מתנות שנשלחו: {user_data[8] or 0:,.0f} SLH
🎁 מתנות שהתקבלו: {user_data[9] or 0:,.0f} SLH

**👥 הצטרף לקהילה:**
{TELEGRAM_GROUP_URL}
        """
    else:
        wallet_text = f"""
**👛 הארנק שלך**

עדיין לא רשומה כתובת ארנק.

**📝 כדי להתחיל:** 
1. שלח את כתובת ה-BSC שלך (מתחיל ב-0x)
2. הצטרף לקהילה: {TELEGRAM_GROUP_URL}
3. התחל לסחור ולקבל מתנות!

**שלח את כתובת הארנק שלך עכשיו...**
        """
    
    update.message.reply_text(wallet_text, parse_mode='Markdown')

def ai_assistant_menu(update, context):
    ai_text = """
**🤖 עוזר AI של SLH**

אני כאן כדי לעזור לך עם:

**📝 עזרה בכתיבת חוזה** 
- תיאורים מקצועיים
- נוסחים משפטיים

**💡 ייעוץ השקעות**
- אסטרטגיות מסחר
- ניתוח הזדמנויות

**🎯 בחר אפשרות או שלח שאלה:**
"/ai [השאלה שלך]"
    """
    update.message.reply_text(ai_text, parse_mode='Markdown', reply_markup=get_ai_keyboard())

def handle_ai_chat(update, context):
    user = update.effective_user
    user_message = update.message.text.replace('/ai', '').strip()
    
    if not user_message:
        update.message.reply_text("🤖 נא לכתוב שאלה אחרי הפקודה /ai")
        return
    
    ai_response = ai_assistant.chat_gpt_response(user_message, "אתה עוזר AI לפלטפורמת מסחר SLH.")
    
    response_text = f"""
**🤖 עוזר AI:**

{ai_response}

**💡 טיפ:** הצטרף לקהילה לדיונים נוספים:
{TELEGRAM_GROUP_URL}
    """
    
    update.message.reply_text(response_text, parse_mode='Markdown')

def community_join(update, context):
    community_text = f"""
**👥 קהילת SLH**

**🌐 הצטרף עכשיו:**
{TELEGRAM_GROUP_URL}

**💎 מה מחכה לך:**
• מאות סוחרים פעילים
• דיונים על מגמות SLH
• הזדמנויות עסקיות
• תמיכה和技术支持

**🚀 שלבי ההצטרפות:**
1. לחץ על '👥 הצטרף לקהילה'
2. הוסף את עצמך לקבוצה
3. חזור לבוט ולחץ '✅ אישור הצטרפות'
    """
    update.message.reply_text(community_text, parse_mode='Markdown', reply_markup=get_community_keyboard())

def user_stats(update, context):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user_data:
        group_status = "✅ חבר בקהילה" if user_data[10] else "❌ טרם הצטרף"
        
        stats_text = f"""
**📊 הסטטיסטיקה שלך**

**👤 פרטים:**
שם: {user_data[2]} {user_data[3] or ''}
משתמש: @{user_data[1] or 'לא רשום'}

**💼 פעילות:**
🎁 מתנות שנשלחו: {user_data[8] or 0:,.0f} SLH
🎁 מתנות שהתקבלו: {user_data[9] or 0:,.0f} SLH

**👥 סטטוס קהילה:** {group_status}

**👥 {group_status}**
{TELEGRAM_GROUP_URL if not user_data[10] else 'תודה שהצטרפת!'}
        """
    else:
        stats_text = "לא נמצאו נתונים עבורך במערכת."
    
    update.message.reply_text(stats_text, parse_mode='Markdown')

def send_gift_menu(update, context):
    gift_text = f"""
**🎁 שליחת מתנות SLH**

**💎 ערך מטבע:** {SLH_VALUE_ILS} ₪
**👥 קהילה:** {TELEGRAM_GROUP_URL}

**🚀 אפשרויות:**
• מתנה מהירה
• מתנה עם הודעה
• מתנה עם תנאים

*פיצ'ר בפיתוח - בקרוב!*
    """
    update.message.reply_text(gift_text, parse_mode='Markdown')

def save_wallet_address(update, context, wallet_address):
    user = update.effective_user
    
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        update.message.reply_text("❌ כתובת ארנק לא תקינה.")
        return
    
    try:
        db.update_wallet(user.id, wallet_address)
        current_balance = advanced_wallet.get_balance(wallet_address)
        
        success_text = f"""
**✅ כתובת הארנק נשמרה!**

**כתובת:** `{wallet_address}`
**💰 יתרה:** {current_balance:,.2f} SLH

**🎉 כעת אתה יכול:**
• לסחור עם חברי הקהילה
• לשלוח ולקבל מתנות
• להיות חלק מהמהפכה!

**👥 הצטרף לקהילה:**
{TELEGRAM_GROUP_URL}
        """
        update.message.reply_text(success_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error saving wallet: {e}")
        update.message.reply_text("❌ שגיאה בשמירת כתובת הארנק.")

def handle_callback(update, context):
    query = update.callback_query
    data = query.data
    user = query.from_user
    
    if data == "back_main":
        query.message.reply_text("חזרת לתפריט הראשי", reply_markup=get_main_keyboard())
    
    elif data == "ai_contract_help":
        help_text = ai_assistant.chat_gpt_response(
            "תן טיפים לכתיבת חוזה SLH",
            "אתה עוזר בכתיבת חוזים"
        )
        query.message.reply_text(f"**🤖 טיפים לכתיבת חוזה:**\n\n{help_text}", parse_mode='Markdown')
    
    elif data == "ai_investment_advice":
        advice = ai_assistant.chat_gpt_response(
            "תן ייעוץ השקעות כללי למטבע SLH",
            "אתה יועץ השקעות"
        )
        query.message.reply_text(f"**💡 ייעוץ השקעות:**\n\n{advice}", parse_mode='Markdown')
    
    elif data == "confirm_join":
        db.mark_joined_group(user.id)
        query.message.reply_text(
            f"✅ **הצטרפות אושרה!**\n\nברוך הבא לקהילת SLH!\n\n"
            f"**👥 קבוצה:** {TELEGRAM_GROUP_URL}",
            parse_mode='Markdown'
        )
    
    query.answer()

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return jsonify({
        "status": "SLH Platform Running", 
        "environment": "PRODUCTION",
        "community": TELEGRAM_GROUP_URL
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == "POST":
        try:
            update = Update.de_json(request.get_json(force=True), bot)
            dispatcher.process_update(update)
            return "OK"
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return "Error", 500
    return "OK"

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = f"https://diana-production.up.railway.app/webhook"
    success = bot.set_webhook(webhook_url)
    logger.info(f"Webhook set: {success} - {webhook_url}")
    return jsonify({"status": "success" if success else "failed", "url": webhook_url})

@app.route('/status')
def status():
    try:
        webhook_info = bot.get_webhook_info()
        return jsonify({
            "status": "active",
            "environment": "production",
            "webhook_url": webhook_info.url,
            "community": TELEGRAM_GROUP_URL
        })
    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

# ==================== PRODUCTION SETUP ====================
def create_app():
    """Factory function for creating the Flask app (for production)"""
    return app

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(CallbackQueryHandler(handle_callback))

if __name__ == '__main__':
    # Production settings
    logger.info("🚀 Starting SLH Bot in PRODUCTION mode...")
    
    # Use environment port or default to 10000
    port = int(os.environ.get('PORT', 10000))
    
    # Run with production settings
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True  # Important for production
    )
