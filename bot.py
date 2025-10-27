import os
import logging
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify
import telegram
from telegram.ext import Dispatcher, MessageHandler, Filters, CommandHandler, CallbackQueryHandler, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from web3 import Web3

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 10000))

# Blockchain Configuration
SLH_TOKEN_ADDRESS = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
BSC_RPC_URL = "https://bsc-dataseed.binance.org/"
SLH_VALUE_ILS = 444

# Community Links
TELEGRAM_GROUP_URL = "https://t.me/+HIzvM8sEgh1kNWY0"
TELEGRAM_GROUP_ID = -1002981609404

# Conversation States
SETTING_CONTACT, GIFT_AMOUNT, GIFT_MESSAGE, TRANSFER_AMOUNT, TRANSFER_RECIPIENT = range(5)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set")

app = Flask(__name__)
bot = telegram.Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# ==================== DATABASE ====================
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                to_user_id INTEGER,
                amount REAL,
                tx_hash TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users (user_id),
                FOREIGN KEY (to_user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES users (user_id)
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
    
    def update_contact_info(self, user_id, phone, website, materials):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET phone = ?, website = ?, materials = ? WHERE user_id = ?
        ''', (phone, website, materials, user_id))
        self.conn.commit()
    
    def mark_joined_group(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET joined_group = TRUE WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
    
    def get_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone()
    
    def get_user_by_wallet(self, wallet_address):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE wallet_address = ?', (wallet_address,))
        return cursor.fetchone()
    
    def add_gift(self, from_user_id, to_user_id, amount, message):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO gifts (from_user_id, to_user_id, amount, message)
            VALUES (?, ?, ?, ?)
        ''', (from_user_id, to_user_id, amount, message))
        
        cursor.execute('''
            UPDATE users SET total_gifts_sent = total_gifts_sent + ? WHERE user_id = ?
        ''', (amount, from_user_id))
        
        cursor.execute('''
            UPDATE users SET total_gifts_received = total_gifts_received + ? WHERE user_id = ?
        ''', (amount, to_user_id))
        
        self.conn.commit()
    
    def add_transaction(self, from_user_id, to_user_id, amount, tx_hash, status='pending'):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (from_user_id, to_user_id, amount, tx_hash, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (from_user_id, to_user_id, amount, tx_hash, status))
        self.conn.commit()

db = UserDatabase()

# ==================== WALLET MANAGER ====================
class SLHWallet:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))
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
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        try:
            self.token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(SLH_TOKEN_ADDRESS),
                abi=self.token_abi
            )
            logger.info("✅ SLH Wallet Manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error initializing wallet: {e}")
    
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
    
    def transfer_tokens(self, from_private_key, to_address, amount):
        try:
            # Get sender address from private key
            account = self.w3.eth.account.from_key(from_private_key)
            sender_address = account.address
            
            # Get decimals
            decimals = self.token_contract.functions.decimals().call()
            amount_wei = int(amount * (10 ** decimals))
            
            # Check balance
            sender_balance = self.get_balance(sender_address)
            if sender_balance < amount:
                return {'success': False, 'error': f'Insufficient balance. You have {sender_balance:.2f} SLH, need {amount:.2f} SLH'}
            
            # Build transaction
            transaction = self.token_contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_wei
            ).build_transaction({
                'from': sender_address,
                'gas': 150000,
                'gasPrice': self.w3.to_wei('5', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(sender_address),
                'chainId': 56
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, from_private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return {
                'success': True,
                'tx_hash': self.w3.to_hex(tx_hash),
                'explorer_url': f'https://bscscan.com/tx/{self.w3.to_hex(tx_hash)}'
            }
            
        except Exception as e:
            logger.error(f"Transfer error: {e}")
            return {'success': False, 'error': str(e)}
    
    def validate_wallet_address(self, address):
        return Web3.is_address(address)

wallet_manager = SLHWallet()

# ==================== KEYBOARDS ====================
def get_main_keyboard():
    keyboard = [
        ["👛 הארנק שלי", "🎁 שלח מתנה"],
        ["💸 העברת SLH", "📊 החוזים שלי"],
        ["👥 הצטרף לקהילה", "⚙️ הגדרות"],
        ["📈 סטטיסטיקות", "ℹ️ מידע"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_wallet_keyboard():
    keyboard = [
        [InlineKeyboardButton("💸 העברת SLH", callback_data="transfer_slh")],
        [InlineKeyboardButton("📤 הפקדה", callback_data="deposit")],
        [InlineKeyboardButton("📥 משיכה", callback_data="withdraw")],
        [InlineKeyboardButton("📊 היסטוריה", callback_data="tx_history")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_transfer_keyboard():
    keyboard = [
        [InlineKeyboardButton("👤 למשתמש בטלגרם", callback_data="transfer_telegram")],
        [InlineKeyboardButton("🏦 לכתובת ארנק", callback_data="transfer_wallet")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_wallet")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_contracts_keyboard():
    keyboard = [
        [InlineKeyboardButton("📋 החוזים הפעילים שלי", callback_data="my_contracts")],
        [InlineKeyboardButton("✅ החוזים שהושלמו", callback_data="completed_contracts")],
        [InlineKeyboardButton("🔍 חפש חוזים", callback_data="search_contracts")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_gift_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎁 מתנה מהירה", callback_data="quick_gift")],
        [InlineKeyboardButton("💌 מתנה עם הודעה", callback_data="gift_with_message")],
        [InlineKeyboardButton("🔗 מתנה עם חוזה", callback_data="gift_with_contract")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("📞 עדכון פרטי קשר", callback_data="update_contact")],
        [InlineKeyboardButton("👥 אישור הצטרפות", callback_data="confirm_join")],
        [InlineKeyboardButton("🔧 ניהול ארנק", callback_data="wallet_management")],
        [InlineKeyboardButton("🔑 הגדרת Private Key", callback_data="set_private_key")],
        [InlineKeyboardButton("🔙 חזרה", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== BOT HANDLERS ====================
def start(update, context):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = f"""
👋 **ברוך הבא {user.first_name}!**

**SLH Platform** - הפלטפורמה המלאה למסחר במטבע SLH

💎 **מטבע SLH:** {SLH_VALUE_ILS} ₪
👥 **קהילה:** {TELEGRAM_GROUP_URL}

**🚀 תכונות מלאות:**
• 👛 ניהול ארנק מתקדם עם העברות
• 🎁 שליחת מתנות SLH
• 💸 העברות ישירות בין משתמשים
• 📝 יצירת חוזים חכמים
• 📊 מעקב אחר עסקאות
• 👥 קהילה פעילה

**בחר אפשרות מהתפריט 👇**
    """
    
    update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

def handle_message(update, context):
    text = update.message.text
    user = update.effective_user
    
    if text == "👛 הארנק שלי":
        my_wallet(update, context)
    elif text == "🎁 שלח מתנה":
        send_gift_menu(update, context)
    elif text == "💸 העברת SLH":
        transfer_menu(update, context)
    elif text == "📝 צור חוזה":
        create_contract(update, context)
    elif text == "📊 החוזים שלי":
        my_contracts(update, context)
    elif text == "👥 הצטרף לקהילה":
        community_join(update, context)
    elif text == "⚙️ הגדרות":
        settings_menu(update, context)
    elif text == "📈 סטטיסטיקות":
        user_stats(update, context)
    elif text == "ℹ️ מידע":
        slh_info(update, context)
    elif text.startswith("0x") and len(text) == 42:
        save_wallet_address(update, context, text)
    else:
        update.message.reply_text("🤔 בחר אחת האפשרויות מהתפריט", reply_markup=get_main_keyboard())

def my_wallet(update, context):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user_data and user_data[4]:
        wallet_address = user_data[4]
        current_balance = wallet_manager.get_balance(wallet_address)
        
        wallet_text = f"""
**👛 הארנק המלא שלך**

**כתובת ארנק:** 
`{wallet_address}`

**💰 יתרת SLH:** {current_balance:,.2f} SLH
**💎 שווי נוכחי:** {current_balance * SLH_VALUE_ILS:,.0f} ₪

**📊 סטטיסטיקות:**
🎁 מתנות שנשלחו: {user_data[8] or 0:,.0f} SLH
🎁 מתנות שהתקבלו: {user_data[9] or 0:,.0f} SLH

**🚀 פעולות:**
• לחץ '💸 העברת SLH' לשליחה ישירה
• לחץ '🎁 שלח מתנה' לשליחת מתנות
• לחץ '📝 צור חוזה' לעסקאות מורכבות
        """
        
        if update.message:
            update.message.reply_text(wallet_text, parse_mode='Markdown', reply_markup=get_wallet_keyboard())
        else:
            update.callback_query.message.reply_text(wallet_text, parse_mode='Markdown', reply_markup=get_wallet_keyboard())
            
    else:
        wallet_text = f"""
**👛 הארנק שלך**

עדיין לא רשומה כתובת ארנק.

**📝 כדי להתחיל:** 
1. שלח את כתובת ה-BSC שלך (מתחיל ב-0x)
2. הצטרף לקהילה: {TELEGRAM_GROUP_URL}
3. התחל לסחור ולקבל מתנות!

**🏦 הוראות ארנק:**
• **רשת:** Binance Smart Chain
• **כתובת מטבע:** `{SLH_TOKEN_ADDRESS}`

**שלח את כתובת הארנק שלך עכשיו...**
        """
        
        if update.message:
            update.message.reply_text(wallet_text, parse_mode='Markdown')
        else:
            update.callback_query.message.reply_text(wallet_text, parse_mode='Markdown')

def transfer_menu(update, context):
    transfer_text = f"""
**💸 מרכז ההעברות של SLH**

**💎 ערך מטבע:** {SLH_VALUE_ILS} ₪
**👥 קהילה:** {TELEGRAM_GROUP_URL}

**🎯 אפשרויות העברה:**
• **👤 למשתמש בטלגרם** - העברה ישירה דרך הבוט
• **🏦 לכתובת ארנק** - העברה לכל כתובת BSC

**⚠️ חשוב:**
• העברות דורשות Private Key מאובטח
• כל עסקה נרשמת בבלוקצ'יין
• עמלות גז נגבות ב-BNB

**💡 טיפ:** הצטרף לקהילה כדי למצוא יותר חברים למסחר!
    """
    
    if update.message:
        update.message.reply_text(transfer_text, parse_mode='Markdown', reply_markup=get_transfer_keyboard())
    else:
        update.callback_query.message.reply_text(transfer_text, parse_mode='Markdown', reply_markup=get_transfer_keyboard())

def start_transfer_to_wallet(update, context):
    query = update.callback_query
    query.message.reply_text(
        "**🏦 העברה לכתובת ארנק**\n\n"
        "שלח את כמות ה-SLH שברצונך להעביר:\n"
        "לדוגמה: `100` או `50.5`\n\n"
        "או שלח 'ביטול' לחזור"
    )
    return TRANSFER_AMOUNT

def handle_transfer_amount(update, context):
    text = update.message.text
    
    if text.lower() == 'ביטול':
        update.message.reply_text("העברה בוטלה", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    try:
        amount = float(text)
        if amount <= 0:
            update.message.reply_text("❌ הכמות חייבת להיות גדולה מ-0. נסה שוב:")
            return TRANSFER_AMOUNT
        
        context.user_data['transfer_amount'] = amount
        
        # Check if user has private key
        user_private_key = context.user_data.get('private_key')
        if not user_private_key:
            update.message.reply_text(
                "❌ **נדרש Private Key**\n\n"
                "להשלמת ההעברה, אנא הגדר את ה-Private Key שלך בהגדרות.\n"
                "➡️ לחץ '⚙️ הגדרות' -> '🔑 הגדרת Private Key'\n\n"
                "העברה בוטלה."
            )
            return ConversationHandler.END
        
        update.message.reply_text(
            f"**כמות:** {amount:,.2f} SLH\n\n"
            "עכשיו שלח את כתובת הארנק של הנמען:\n"
            "לדוגמה: `0x742d35Cc6634C0532925a3b8D4B19a5f4B3a7A64`"
        )
        return TRANSFER_RECIPIENT
            
    except ValueError:
        update.message.reply_text("❌ כמות לא תקינה. נסה שוב:")
        return TRANSFER_AMOUNT

def handle_transfer_recipient(update, context):
    text = update.message.text
    user = update.effective_user
    
    if text.lower() == 'ביטול':
        update.message.reply_text("🚫 ההעברה בוטלה", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    # This is the recipient address
    to_address = text.strip()
    
    if not wallet_manager.validate_wallet_address(to_address):
        update.message.reply_text("❌ כתובת ארנק לא תקינה. נסה שוב:")
        return TRANSFER_RECIPIENT
    
    context.user_data['transfer_address'] = to_address
    amount = context.user_data['transfer_amount']
    private_key = context.user_data.get('private_key')
    
    # Get sender address for balance check
    try:
        sender_address = wallet_manager.w3.eth.account.from_key(private_key).address
        sender_balance = wallet_manager.get_balance(sender_address)
        
        if sender_balance < amount:
            update.message.reply_text(
                f"❌ **יתרה לא מספקת!**\n\n"
                f"**יתרה שלך:** {sender_balance:.2f} SLH\n"
                f"**נדרש:** {amount:.2f} SLH\n\n"
                "העברה בוטלה."
            )
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Balance check error: {e}")
        update.message.reply_text("❌ שגיאה בבדיקת יתרה. נסה שוב.")
        return ConversationHandler.END
    
    confirm_text = f"""
**✅ אישור העברה**

**📤 משלח:** אתה
**📥 מקבל:** `{to_address}`
**💰 כמות:** {amount:,.2f} SLH
**💎 שווי:** {amount * SLH_VALUE_ILS:,.0f} ₪

**⚠️ אישור:** שלח '✅ אישור' להשלמת ההעברה
**🚫 ביטול:** שלח '❌ ביטול' לביטול

_⛽ העברה כוללת עמלת גז ב-BNB_
    """
    
    update.message.reply_text(confirm_text, parse_mode='Markdown')
    return "CONFIRM_TRANSFER"

def confirm_transfer(update, context):
    text = update.message.text
    user = update.effective_user
    
    if text == '✅ אישור':
        # Execute transfer
        amount = context.user_data['transfer_amount']
        to_address = context.user_data['transfer_address']
        private_key = context.user_data.get('private_key')
        
        try:
            update.message.reply_text("🔄 **מבצע העברה...**\n\n_פעולה זו עשויה לארוך מספר שניות..._")
            
            # Execute blockchain transfer
            result = wallet_manager.transfer_tokens(private_key, to_address, amount)
            
            if result['success']:
                # Record transaction in database
                user_data = db.get_user(user.id)
                if user_data and user_data[4]:
                    db.add_transaction(user.id, None, amount, result['tx_hash'], 'completed')
                
                success_text = f"""
**✅ ההעברה בוצעה בהצלחה!**

**📤 משלח:** אתה
**📥 מקבל:** `{to_address}`
**💰 כמות:** {amount:,.2f} SLH
**💎 שווי:** {amount * SLH_VALUE_ILS:,.0f} ₪
**🔗 Hash עסקה:** `{result['tx_hash']}`

**📊 ניתן לעקוב אחר העסקה ב-** 
{result['explorer_url']}

_🕐 העסקה תאושר בעוד מספר דקות_
                """
                update.message.reply_text(success_text, parse_mode='Markdown')
            else:
                error_text = f"""
**❌ ההעברה נכשלה**

**שגיאה:** {result['error']}

**🚦עדים אפשריים:**
• וודא שיש לך מספיק BNB לעמלות גז
• בדוק שהכתובת נכונה
• נסה שוב בעוד מספר דקות
                """
                update.message.reply_text(error_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Transfer execution error: {e}")
            update.message.reply_text("❌ שגיאה בביצוע ההעברה. נסה שוב מאוחר יותר.")
            
    elif text == '❌ ביטול':
        update.message.reply_text("🚫 ההעברה בוטלה", reply_markup=get_main_keyboard())
    else:
        update.message.reply_text("❌ אנא שלח '✅ אישור' או '❌ ביטול'")
        return "CONFIRM_TRANSFER"
    
    return ConversationHandler.END

def set_private_key(update, context):
    query = update.callback_query
    query.message.reply_text(
        "**🔑 הגדרת Private Key**\n\n"
        "⚠️ **אזהרת אבטחה:**\n"
        "• Private Key נשמר באופן מקומי בלבד\n"
        "• לא משותף עם אף אחד\n"
        "• נחלף להעברות בלבד\n\n"
        "**📝 שלח את ה-Private Key שלך** (מתחיל ב-0x)...\n"
        "או שלח 'ביטול' לחזור"
    )
    return "SET_PRIVATE_KEY"

def handle_private_key_input(update, context):
    text = update.message.text
    
    if text.lower() == 'ביטול':
        update.message.reply_text("ביטול הגדרת Private Key", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    
    if text.startswith('0x') and len(text) == 66:
        context.user_data['private_key'] = text
        
        # Verify the private key works by getting the address
        try:
            account = wallet_manager.w3.eth.account.from_key(text)
            wallet_address = account.address
            
            update.message.reply_text(
                f"✅ **Private Key נשמר בהצלחה!**\n\n"
                f"**כתובת הארנק שלך:** `{wallet_address}`\n\n"
                "המפתח נשמר באופן מקומי ובטוח.\n"
                "כעת תוכל לבצע העברות SLH.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            update.message.reply_text(
                "❌ Private Key לא תקין. נסה שוב:",
                parse_mode='Markdown'
            )
            return "SET_PRIVATE_KEY"
    else:
        update.message.reply_text("❌ Private Key לא תקין. נסה שוב:")
        return "SET_PRIVATE_KEY"
    
    return ConversationHandler.END

def send_gift_menu(update, context):
    gift_text = f"""
**🎁 מרכז המתנות של SLH**

**💎 ערך מטבע:** {SLH_VALUE_ILS} ₪
**👥 קהילה:** {TELEGRAM_GROUP_URL}

**🎯 אפשרויות שליחה:**
• **מתנה מהירה** - שליחה ישירה
• **מתנה עם הודעה** - עם ברכה אישית  
• **מתנה עם חוזה** - עם תנאים ושלבים

**💡 טיפ:** הצטרף לקהילה כדי למצוא יותר חברים לשליחת מתנות!
    """
    if update.message:
        update.message.reply_text(gift_text, parse_mode='Markdown', reply_markup=get_gift_keyboard())
    else:
        update.callback_query.message.reply_text(gift_text, parse_mode='Markdown', reply_markup=get_gift_keyboard())

def create_contract(update, context):
    contract_text = f"""
**📝 יצירת חוזה חדש**

חוזה חכם מאפשר לך ליצור עסקאות עם תנאים ושלבים.

**📋 סוגי חוזים:**
• חוזי עבודה עם תשלומים לפי שלבים
• חוזי שותפות עם חלוקת רווחים
• חוזי מתנה עם תנאים
• חוזים מותאמים אישית

**👥 מומלץ:** הצטרף לקהילה למציאת שותפים:
{TELEGRAM_GROUP_URL}

*פיצ'ר בשלבי פיתוח - יגיע soon!*
    """
    if update.message:
        update.message.reply_text(contract_text, parse_mode='Markdown')
    else:
        update.callback_query.message.reply_text(contract_text, parse_mode='Markdown')

def my_contracts(update, context):
    contracts_text = """
**📊 ניהול חוזים**

באפשרותך ליצור חוזים חכמים עם שלבים, לעקוב אחר התקדמות ולנהל עסקאות מורכבות.

**🚀 בחר פעולה:**
    """
    if update.message:
        update.message.reply_text(contracts_text, parse_mode='Markdown', reply_markup=get_contracts_keyboard())
    else:
        update.callback_query.message.reply_text(contracts_text, parse_mode='Markdown', reply_markup=get_contracts_keyboard())

def community_join(update, context):
    community_text = f"""
**👥 קהילת SLH - המקום שלנו!**

**🌐 הצטרף עכשיו:**
{TELEGRAM_GROUP_URL}

**💎 מה מחכה לך בקהילה:**
• מאות סוחרים פעילים
• דיונים על מגמות SLH
• הזדמנויות עסקיות
• תמיכה和技术支持
• חדשות ועדכונים

**🚀 שלבי ההצטרפות:**
1. לחץ על '👥 הצטרף לקהילה'
2. הוסף את עצמך לקבוצה
3. חזור לבוט ולחץ '✅ אישור הצטרפות'
4. קבל גישה מלאה!

**📞 מתקשה?** שלח הודעה למנהלים בקבוצה.
    """
    if update.message:
        update.message.reply_text(community_text, parse_mode='Markdown')
    else:
        update.callback_query.message.reply_text(community_text, parse_mode='Markdown')

def settings_menu(update, context):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    has_private_key = "✅ מוגדר" if update.context.user_data.get('private_key') else "❌ לא מוגדר"
    
    settings_text = f"""
**⚙️ הגדרות אישיות**

**👤 פרטים נוכחיים:**
📞 טלפון: {user_data[5] or 'לא הוגדר'}
🌐 אתר: {user_data[6] or 'לא הוגדר'}
📁 חומרים: {user_data[7] or 'לא הוגדר'}
🔑 Private Key: {has_private_key}

**👥 קהילה:** {TELEGRAM_GROUP_URL}

**🔧 אפשרויות:**
• עדכון פרטי קשר
• אישור הצטרפות לקהילה
• ניהול ארנק
• הגדרות נוספות

**בחר פעולה:**
    """
    if update.message:
        update.message.reply_text(settings_text, parse_mode='Markdown', reply_markup=get_settings_keyboard())
    else:
        update.callback_query.message.reply_text(settings_text, parse_mode='Markdown', reply_markup=get_settings_keyboard())

def user_stats(update, context):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user_data:
        group_status = "✅ חבר בקהילה" if user_data[10] else "❌ טרם הצטרף"
        
        stats_text = f"""
**📊 הסטטיסטיקה המלאה שלך**

**👤 פרטים:**
שם: {user_data[2]} {user_data[3] or ''}
משתמש: @{user_data[1] or 'לא רשום'}
סטטוס קהילה: {group_status}

**💼 פעילות:**
🎁 מתנות שנשלחו: {user_data[8] or 0:,.0f} SLH
🎁 מתנות שהתקבלו: {user_data[9] or 0:,.0f} SLH
📊 מספר חוזים: *בקרוב*

**👥 {group_status}**
{TELEGRAM_GROUP_URL if not user_data[10] else 'תודה שהצטרפת!'}
        """
    else:
        stats_text = "לא נמצאו נתונים עבורך במערכת."
    
    if update.message:
        update.message.reply_text(stats_text, parse_mode='Markdown')
    else:
        update.callback_query.message.reply_text(stats_text, parse_mode='Markdown')

def slh_info(update, context):
    slh_text = f"""
**ℹ️ מידע מלא על מטבע SLH**

**💎 מטבע SLH - Smart Life Hub**

**מידע בסיסי:**
• **שם:** SLH Token
• **סימבול:** SLH
• **רשת:** Binance Smart Chain
• **ערך נוכחי:** {SLH_VALUE_ILS} ₪

**🏦 הוראות טכניות:**
• **כתובת חוזה:** `{SLH_TOKEN_ADDRESS}`
• **Chain ID:** 56
• **RPC URL:** https://bsc-dataseed.binance.org/

**💎 יתרונות למחזיקים:**
• גישה לשירותים premium
• הנחות מיוחדות על שירותים
• השתתפות בקהילה פעילה
• הטבות נוספות

**👥 הצטרף לקהילה:** {TELEGRAM_GROUP_URL}
    """
    if update.message:
        update.message.reply_text(slh_text, parse_mode='Markdown')
    else:
        update.callback_query.message.reply_text(slh_text, parse_mode='Markdown')

def save_wallet_address(update, context, wallet_address):
    user = update.effective_user
    
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        update.message.reply_text("❌ כתובת ארנק לא תקינה. אנא שלח כתובת בפורמט הנכון.")
        return
    
    try:
        db.update_wallet(user.id, wallet_address)
        current_balance = wallet_manager.get_balance(wallet_address)
        
        success_text = f"""
**✅ כתובת הארנק נשמרה בהצלחה!**

**כתובת:** `{wallet_address}`

**💰 יתרה נוכחית:** {current_balance:,.2f} SLH

**🎉 כעת אתה יכול:**
• לסחור בחופשיות עם חברי הקהילה
• לשלוח ולקבל מתנות
• ליצור חוזים חכמים
• להיות חלק מהמהפכה!

**👥 הצטרף לקהילה שלנו:**
{TELEGRAM_GROUP_URL}
        """
        update.message.reply_text(success_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error saving wallet: {e}")
        update.message.reply_text("❌ אירעה שגיאה בשמירת כתובת הארנק. נסה שוב.")

def handle_contact_update(update, context):
    text = update.message.text
    user = update.effective_user
    
    try:
        lines = text.split('\n')
        contact_info = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                contact_info[key.strip()] = value.strip()
        
        phone = contact_info.get('טלפון', '')
        website = contact_info.get('אתר', '')
        materials = contact_info.get('חומרים', '')
        
        db.update_contact_info(user.id, phone, website, materials)
        
        success_text = f"""
**✅ הפרטים נשמרו בהצלחה!**

**👤 הפרטים שלך:**
📞 טלפון: {phone}
🌐 אתר: {website}  
📁 חומרים: {materials}

**💼 כעת תוכל:**
• לשתף את הפרטים שלך
• לבנות נוכחות מקצועית
• למצוא שותפים לעסקאות

**👥 הצטרף לקהילה לחיבור עם סוחרים:**
{TELEGRAM_GROUP_URL}
        """
        
        update.message.reply_text(success_text, parse_mode='Markdown')
        return ConversationHandler.END
        
    except Exception as e:
        update.message.reply_text("❌ שגיאה בשמירת הפרטים. נסה שוב בפורמט הנכון.")
        return SETTING_CONTACT

def handle_callback(update, context):
    query = update.callback_query
    data = query.data
    user = query.from_user
    
    if data == "back_main":
        query.message.reply_text("🔙 חזרת לתפריט הראשי", reply_markup=get_main_keyboard())
    
    elif data == "back_wallet":
        my_wallet(update, context)
    
    elif data == "transfer_slh":
        transfer_menu(update, context)
    
    elif data == "transfer_wallet":
        start_transfer_to_wallet(update, context)
        return TRANSFER_AMOUNT
    
    elif data == "set_private_key":
        set_private_key(update, context)
        return "SET_PRIVATE_KEY"
    
    elif data == "my_contracts":
        query.message.reply_text("📋 **החוזים הפעילים שלך:**\n\n*בקרוב - פיצ'ר בפיתוח*", parse_mode='Markdown')
    
    elif data == "quick_gift":
        query.message.reply_text("🎁 **מתנה מהירה:**\n\n*בקרוב - פיצ'ר בפיתוח*", parse_mode='Markdown')
    
    elif data == "update_contact":
        query.message.reply_text(
            "**📞 עדכון פרטי קשר**\n\n"
            "שלח את הפרטים שלך בפורמט:\n"
            "`טלפון: 050-1234567\n"
            "אתר: https://mysite.com\n"
            "חומרים: קישור לתיק עבודה`",
            parse_mode='Markdown'
        )
    
    elif data == "confirm_join":
        db.mark_joined_group(user.id)
        query.message.reply_text(
            f"✅ **הצטרפות אושרה!**\n\nברוך הבא לקהילת SLH {user.first_name}!\n\n"
            f"**👥 קבוצה:** {TELEGRAM_GROUP_URL}\n"
            f"**🚀 כעת תוכל:**\n• להתחבר עם סוחרים\n• לשתף בהזדמנויות\n• לקבל תמיכה מהקהילה",
            parse_mode='Markdown'
        )
    
    query.answer()

# ==================== CONVERSATION HANDLERS ====================
contact_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(lambda u,c: u.callback_query.message.reply_text(
            "**📞 עדכון פרטי קשר**\n\nשלח את הפרטים בפורמט:\nטלפון: 050-1234567\nאתר: https://example.com\nחומרים: תיאור"
        ), pattern='^update_contact$')
    ],
    states={
        SETTING_CONTACT: [MessageHandler(Filters.text & ~Filters.command, handle_contact_update)],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("ביטול", reply_markup=get_main_keyboard()))]
)

transfer_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_transfer_to_wallet, pattern='^transfer_wallet$')
    ],
    states={
        TRANSFER_AMOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_amount)],
        TRANSFER_RECIPIENT: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_recipient)],
        "CONFIRM_TRANSFER": [MessageHandler(Filters.text & ~Filters.command, confirm_transfer)],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("העברה בוטלה", reply_markup=get_main_keyboard()))]
)

private_key_conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(set_private_key, pattern='^set_private_key$')
    ],
    states={
        "SET_PRIVATE_KEY": [MessageHandler(Filters.text & ~Filters.command, handle_private_key_input)],
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("ביטול", reply_markup=get_main_keyboard()))]
)

# ==================== REGISTER HANDLERS ====================
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(contact_conv_handler)
dispatcher.add_handler(transfer_conv_handler)
dispatcher.add_handler(private_key_conv_handler)
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dispatcher.add_handler(CallbackQueryHandler(handle_callback))

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return jsonify({
        "status": "SLH Platform - FULLY ACTIVE 🟢",
        "bot": f"@{bot.get_me().username}",
        "features": "Wallet, Transfers, Gifts, Contracts, Community",
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
    try:
        webhook_url = f"https://{request.host}/webhook"
        bot.delete_webhook()
        success = bot.set_webhook(webhook_url)
        
        if success:
            return jsonify({
                "status": "success 🟢",
                "message": "Webhook configured!",
                "bot": f"@{bot.get_me().username}",
                "url": webhook_url
            })
        else:
            return jsonify({"status": "error 🔴"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status')
def status():
    try:
        webhook_info = bot.get_webhook_info()
        return jsonify({
            "status": "FULLY ACTIVE 🟢",
            "bot": f"@{bot.get_me().username}",
            "webhook_url": webhook_info.url,
            "webhook_set": bool(webhook_info.url),
            "features": "Wallet, Transfers, Gifts, Contracts, Community, Settings"
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting FULL SLH Bot with TRANSFER capabilities...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
