from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DBSession
from dotenv import load_dotenv
import os
from openai import OpenAI
from session_database import async_session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from models import Session as GameSession, Message
from turn_manager import TurnManager

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

turn_managers = {}

# Dependency to get a DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
def get_turn_manager(session_id: str, db: DBSession) -> TurnManager:
    if session_id not in turn_managers:
        # Try to fetch existing state from the DB
        session = db.query(GameSession).filter_by(session_id=session_id).first()

        if session:
            turn_manager = TurnManager(
                turn_number=session.current_turn,
                pacing=session.pacing_mode,
                current_date_str=session.in_game_date
            )
        else:
            # If not in DB yet, create with default state
            turn_manager = TurnManager()

        turn_managers[session_id] = turn_manager

    return turn_managers[session_id]
@app.post("/talk/gamemaster")
async def talk_gamemaster(request: Request, db: DBSession = Depends(get_db)):
    data = await request.json()
    player_input = data.get("message", "")
    session_id = data.get("session_id", "default")  # temp default for simplicity

    if not player_input:
        return {"error": "No message provided"}

    # Advance turn if applicable
    turn_manager = get_turn_manager(session_id, db)

    if turn_manager.should_advance_turn(player_input):
        turn_manager.next_turn()
    system_msg = turn_manager.get_system_message()
    pacing_note = turn_manager.get_pacing_instruction()
    full_sys_msg = f"{system_msg}\n{pacing_note}".strip()
    wrapped_sys_msg = f"\n\n{{{full_sys_msg}}}" if full_sys_msg else ""
    wrapped_player_input = f"{player_input.strip()}{wrapped_sys_msg}"

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
        ai_response = completion.choices[0].message.content

        # Log messages to database
        game_session = db.query(GameSession).filter_by(session_id=session_id).first()
        if not game_session:
            game_session = GameSession(session_id=session_id, agency="SIS", pacing_mode="green", user_id="local")
            db.add(game_session)
            db.commit()

        turn_num = turn_manager.current_turn()

        db.add_all([
            Message(session_id=session_id, sender="user", content=player_input, turn_number=turn_num, pacing_mode=turn_manager.current_mode(), in_game_date=turn_manager.current_date()),
            Message(session_id=session_id, sender="ai", content=ai_response, turn_number=turn_num, pacing_mode=turn_manager.current_mode(), in_game_date=turn_manager.current_date()),
        ])
        db.commit()

        turn_manager.handle_ai_response(ai_response)
        game_session.current_turn = turn_manager.current_turn()
        game_session.pacing_mode = turn_manager.current_mode()
        game_session.in_game_date = turn_manager.current_date_str()
        db.commit()
        return {"response": ai_response}

    except Exception as e:
        return {"error": str(e)}

@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})