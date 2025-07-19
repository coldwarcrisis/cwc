from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
from openai import OpenAI

from turn_manager import TurnManager  # Make sure it's the updated version

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

with open("system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = {"role": "system", "content": f.read()}

# Initialize the turn manager globally
turn_manager = TurnManager()

@app.post("/talk/gamemaster")
async def talk_gamemaster(request: Request):
    data = await request.json()
    player_input = data.get("message", "")
    if not player_input:
        return {"error": "No message provided"}

    # Check if turn should advance
    if turn_manager.should_advance_turn(player_input):
        turn_manager.next_turn()

    # Get the current turn’s system message (if any)
    system_message = turn_manager.get_system_message()

    # Inject pacing instructions and wrap in {} for AI parsing
    pacing_note = turn_manager.get_pacing_instruction()
    full_system_instruction = f"{system_message}\n{pacing_note}".strip()
    wrapped_system_instruction = f"\n\n{{{full_system_instruction}}}" if full_system_instruction else ""

    # Append system instruction to the user’s message
    wrapped_player_input = f"{player_input.strip()}{wrapped_system_instruction}"

    messages = [
        SYSTEM_PROMPT,
        {"role": "user", "content": wrapped_player_input},
    ]

    try:
        completion = client.chat.completions.create(
            model="tngtech/deepseek-r1t2-chimera:free",
            messages=messages,
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Cold War GM API",
            },
        )
        content = completion.choices[0].message.content

        # Check for pacing override requests from AI
        turn_manager.handle_ai_response(content)

        return {"response": content}
    except Exception as e:
        return {"error": str(e)}