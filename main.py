from fastapi import FastAPI, Request
import os
from dotenv import load_dotenv
from openai import OpenAI  # Assuming 'openai' is the OpenRouter client package

load_dotenv()

app = FastAPI()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are the Cold War Game Master. "
        "You narrate events, respond to player inputs, and maintain a rich historical atmosphere. "
        "Keep replies concise and in character."
    ),
}

@app.post("/talk/gamemaster")
async def talk_gamemaster(request: Request):
    data = await request.json()
    player_input = data.get("message", "")
    if not player_input:
        return {"error": "No message provided"}

    messages = [
        SYSTEM_PROMPT,
        {"role": "user", "content": player_input},
    ]

    try:
        completion = client.chat.completions.create(
            model="tngtech/deepseek-r1t2-chimera:free",
            messages=messages,
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Cold War GM API",
            },
            extra_body={},  # can be omitted if not needed
        )
    except Exception as e:
        return {"error": str(e)}

    content = completion.choices[0].message.content
    return {"response": content}
    @app.get("/ping")
    async def ping():
    return {"ping": "pong"}