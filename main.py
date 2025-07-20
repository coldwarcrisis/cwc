from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import os
from openai import OpenAI
from session_database import async_session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from models import Session as GameSession, Message
from turn_manager import TurnManager
from sqlalchemy import select
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
def get_turn_manager(session_id: str, game_session: GameSession) -> TurnManager:
    if session_id not in turn_managers:
        turn_manager = TurnManager(
            turn_number=game_session.current_turn,
            pacing=game_session.pacing_mode,
            current_date_str=game_session.in_game_date
        )
        turn_managers[session_id] = turn_manager

    return turn_managers[session_id]
@app.post("/talk/gamemaster")
async def talk_gamemaster(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    player_input = data.get("message", "")
    session_id = data.get("session_id", "default")

    if not player_input:
        return {"error": "No message provided"}

    # Try to load the session
    result = await db.execute(select(GameSession).filter_by(session_id=session_id))
    game_session = result.scalars().first()

    if not game_session:
        game_session = GameSession(
            session_id=session_id,
            agency="SIS",
            pacing_mode="green",
            user_id="local",
            current_turn=0,
            in_game_date="1955-05-04",
        )
        db.add(game_session)
        await db.commit()

    # Initialize the turn manager
    turn_manager = get_turn_manager(session_id, game_session)

    if turn_manager.should_advance_turn(player_input):
        turn_manager.next_turn()

    # Prepare message for AI
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
        print("Full completion response:", completion)   # <---- here
        ai_response = completion.choices[0].message.content
        print("AI response extracted:", ai_response) 
        turn_manager.handle_ai_response(ai_response)
        turn_num = turn_manager.current_turn()

        db.add_all([
            Message(
                session_id=session_id,
                sender="user",
                content=player_input,
                turn_number=turn_num,
                pacing_mode=turn_manager.current_mode(),
                in_game_date=turn_manager.current_date()
            ),
            Message(
                session_id=session_id,
                sender="ai",
                content=ai_response,
                turn_number=turn_num,
                pacing_mode=turn_manager.current_mode(),
                in_game_date=turn_manager.current_date()
            ),
        ])
        await db.commit()

        # Update session
        game_session.current_turn = turn_manager.current_turn()
        game_session.pacing_mode = turn_manager.current_mode()
        game_session.in_game_date = turn_manager.current_date_str()
        await db.commit()

        return {"response": ai_response}

    except Exception as e:
        return {"error": str(e)}

@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})