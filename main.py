import asyncio
from fastapi import FastAPI
import uvicorn
from config import TELEGRAM_BOT_TOKEN
from bot import run_polling

app = FastAPI()

@app.get("/")
def root():
    return {"message": "SLH Bot API running"}

# הרצת הבוט בפולינג כמשימה רקע
@app.on_event("startup")
async def startup_event():
    token = TELEGRAM_BOT_TOKEN
    if not token:
        print("TELEGRAM_BOT_TOKEN לא מוגדר")
        return
    # הפעלת הפולינג ברקע
    asyncio.create_task(run_polling(token))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
