import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

async def ask_ai(prompt):
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"שגיאה ב־AI: {str(e)}"
