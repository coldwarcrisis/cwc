import asyncio
from session_database import engine, Base

import models

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # optional: clears tables
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(create_tables())