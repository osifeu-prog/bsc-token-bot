import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

async def ask_ai(prompt):
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content
