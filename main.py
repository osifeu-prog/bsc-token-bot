import logging
from fastapi import FastAPI, Request, HTTPException
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, BasePersistence, DictPersistence
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_PATH, TELEGRAM_WEBHOOK_URL
from bot import register_handlers
from users import init_db as init_users_db, engine as users_engine
from store import init_db as init_store_db
from history import init_db as init_history_db
from users import init_db as _u  # ensure imports
import uvicorn

logging.basicConfig(level=logging.INFO)
app = FastAPI()
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Setup persistence for Conversation data (in-memory dict persistence can be replaced by Redis)
persistence = DictPersistence()

# Build application for handler registration
application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).persistence(persistence).build()
register_handlers(application)

# Initialize DBs
init_users_db()
init_store_db()
init_history_db()

@app.on_event("startup")
async def startup():
    # set webhook on startup if TELEGRAM_WEBHOOK_URL provided
    if TELEGRAM_WEBHOOK_URL:
        logging.info("Setting Telegram webhook to %s", TELEGRAM_WEBHOOK_URL)
        await bot.set_webhook(TELEGRAM_WEBHOOK_URL)
    else:
        logging.info("No TELEGRAM_WEBHOOK_URL provided; ensure you will use polling instead")

@app.post(TELEGRAM_WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    body = await request.json()
    update = Update.de_json(body, bot)
    try:
        await application.process_update(update)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}

@app.get("/")
def read_root():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
