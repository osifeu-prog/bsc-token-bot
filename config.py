import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")  # e.g., https://<railway-app>.up.railway.app/webhook

# Wallet / BSC
OWNER_WALLET_ADDRESS = os.getenv("OWNER_WALLET_ADDRESS")
OWNER_WALLET_PRIVATE_KEY = os.getenv("OWNER_WALLET_PRIVATE_KEY")
TOKEN_CONTRACT_ADDRESS = os.getenv("TOKEN_CONTRACT_ADDRESS")
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
CHAIN_ID = int(os.getenv("CHAIN_ID", 56))
SYMBOL = os.getenv("SYMBOL", "SLH")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# IPFS / Pinata (or other pinning service)
PINATA_API_KEY = os.getenv("PINATA_API_KEY")
PINATA_API_SECRET = os.getenv("PINATA_API_SECRET")

# Database (Postgres)
DATABASE_URL = os.getenv("DATABASE_URL")  # postgres://user:pass@host:port/dbname
