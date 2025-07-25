from fastapi import FastAPI, Request, Depends, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import os
from openai import OpenAI
from session_database import async_session
from typing import AsyncGenerator
from models import Session as GameSession, Message
from turn_manager import TurnManager
from sqlalchemy import select
from functools import partial
import asyncio
import time
from pathlib import Path
load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)



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

def load_agency_prompt(agency: str | None) -> dict:
    agency = agency.upper() if agency else "DEFAULT"
    allowed_agencies = {"CIA", "KGB", "SIS"}
    filename = f"{agency}_prompt.txt" if agency in allowed_agencies else "system_prompt.txt"
    filepath = Path(filename)

    if not filepath.is_file():
        filepath = Path("system_prompt.txt")  # fallback if missing

    with filepath.open("r", encoding="utf-8") as f:
        return {"role": "system", "content": f.read()}
@app.post("/talk/gamemaster")
async def talk_gamemaster(request: Request, db: AsyncSession = Depends(get_db)):
    start = time.perf_counter() #latency debug start
    data = await request.json()
    player_input = data.get("message", "")
    session_id = data.get("session_id", "default")
    force_end_turn = data.get("force_end_turn", False)
    if not player_input:
        return {"error": "No message provided"}

    # Try to load the session
    result = await db.execute(select(GameSession).filter_by(session_id=session_id))
    game_session = result.scalars().first()

    if not game_session:
        game_session = GameSession(
            session_id=session_id,
            agency=None,
            pacing_mode="green",
            user_id="local",
            current_turn=0,
            in_game_date="1955-05-04",
        )
        db.add(game_session)
        await db.commit()
    
   

    # Initialize the turn manager
    turn_manager = get_turn_manager(session_id, game_session)

    if force_end_turn or turn_manager.should_advance_turn(player_input):
        turn_manager.next_turn()

    # Prepare message for AI
    system_msg = turn_manager.get_system_message()
    pacing_note = turn_manager.get_pacing_instruction()
    full_sys_msg = f"{system_msg}\n{pacing_note}".strip()
    wrapped_sys_msg = f"\n\n{{{full_sys_msg}}}" if full_sys_msg else ""
    wrapped_player_input = f"{player_input.strip()}{wrapped_sys_msg}"
    system_prompt = load_agency_prompt(game_session.agency)
    messages = [
        system_prompt,
        {"role": "user", "content": wrapped_player_input},
    ]   
    mid1 = time.perf_counter()
    # pre AI call
    try:
        loop = asyncio.get_running_loop()
        completion = await loop.run_in_executor(None, partial(
            client.chat.completions.create,
            model="tngtech/deepseek-r1t2-chimera:free",
            messages=messages,
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Cold War GM API",
            },
        ))
        mid2 = time.perf_counter()
        # raw AI receive
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
                in_game_date=turn_manager.current_date
            ),
            Message(
                session_id=session_id,
                sender="ai",
                content=ai_response,
                turn_number=turn_num,
                pacing_mode=turn_manager.current_mode(),
                in_game_date=turn_manager.current_date
            ),
        ])
        await db.commit()

        # Update session
        game_session.current_turn = turn_manager.current_turn()
        game_session.pacing_mode = turn_manager.current_mode()
        game_session.in_game_date = turn_manager.current_date_str()
        await db.commit()
        end = time.perf_counter()
        print(f"Start to Pre AI: {mid1 - start:.2f}s, Pre AI to Post AI: {mid2 - mid1:.2f}s, Post AI to end: {end - mid2:.2f}s")
        return {"response": ai_response}

    except Exception as e:
        import traceback
        print("Exception occurred:", e)
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/", response_class=HTMLResponse)
async def get_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})
@app.get("/session/{session_id}")
async def load_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).filter_by(session_id=session_id))
    game_session = result.scalars().first()
    if not game_session:
        return JSONResponse(content={
            "session_id": session_id,
            "messages": [],
            "session_metadata": {
                "pacing_mode": None,
                "current_turn": 0,
                "in_game_date": None,
                "agency": None,
            }
        })

    result = await db.execute(
        select(Message)
        .filter_by(session_id=session_id)
        .order_by(Message.timestamp.asc())
    )
    messages = result.scalars().all()
    get_turn_manager(session_id, game_session)
    return {
        "session_id": session_id,
        "messages": [
            {"sender": m.sender, "content": m.content, "timestamp": m.timestamp.isoformat()}
            for m in messages
        ],
        "session_metadata": {
            "pacing_mode": game_session.pacing_mode,
            "current_turn": game_session.current_turn,
            "in_game_date": game_session.in_game_date,
            "agency": game_session.agency,
        }
    }
@app.post("/session/set-newgame")
async def set_newgame(data: dict = Body(...), db: AsyncSession = Depends(get_db)):
    session_id = data.get("session_id")
    agency = data.get("agency")

    if not session_id or not agency:
        return {"success": False, "error": "Missing session_id or agency"}

    result = await db.execute(select(GameSession).filter_by(session_id=session_id))
    game_session = result.scalars().first()

    if not game_session:
        # Create the session if it doesn't exist yet
        game_session = GameSession(
            session_id=session_id,
            agency=agency,
            pacing_mode="green",
            user_id="local",
            current_turn=0,
            in_game_date="1955-05-04",
        )
        db.add(game_session)
        await db.commit()
        return {"success": True, "created": True}

    game_session.agency = agency
    await db.commit()
    return {"success": True, "updated": True}
