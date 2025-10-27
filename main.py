from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder
from config import TELEGRAM_BOT_TOKEN
from bot import get_handlers

app = FastAPI()
telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

for handler in get_handlers():
    telegram_app.add_handler(handler)

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "SLH Bot API is running"}
