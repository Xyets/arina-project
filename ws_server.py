import asyncio
from app.main_lov import ws_server  # импорт твоей async-функции

if __name__ == "__main__":
    asyncio.run(ws_server())
