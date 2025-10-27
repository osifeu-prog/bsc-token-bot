import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_WALLET_ADDRESS = os.getenv("OWNER_WALLET_ADDRESS")
OWNER_WALLET_PRIVATE_KEY = os.getenv("OWNER_WALLET_PRIVATE_KEY")
TOKEN_CONTRACT_ADDRESS = os.getenv("TOKEN_CONTRACT_ADDRESS")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
CHAIN_ID = int(os.getenv("CHAIN_ID", 56))
SYMBOL = os.getenv("SYMBOL", "SLH")
