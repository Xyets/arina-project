import asyncio
import websockets
import websocket
import json
import threading

# 🔧 Вставь сюда актуальный WebSocket URL с control_token
FC2_WS_URL = "wss://us-west-1-media-worker1059.live.fc2.com/control/channels/2_42811971?control_token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjQyODExOTcxNjkxNzFmNTRiZWZhYjMuMTIxOTExNTIiLCJjaGFubmVsX2lkIjoiMl80MjgxMTk3MSIsInVzZXJfaWQiOiI0MjgxMTk3MSIsInNlcnZpY2VfaWQiOiIzOTMwODE3OCIsIm9yel90b2tlbiI6ImJlN2M2OGZlN2RjZDNhYmRhZDZkOGMzNjIwYTZhMTBiZDgwYzkyMDQiLCJwcmVtaXVtIjowLCJtb2RlIjoicHVibGlzaCIsImxhbmd1YWdlIjoicnUiLCJjbGllbnRfdHlwZSI6InBjIiwiY2xpZW50X2FwcCI6ImJyb3dzZXIiLCJjbGllbnRfdmVyc2lvbiI6IjIuNS4wICBbMV0iLCJhcHBfaW5zdGFsbF9rZXkiOiIiLCJjaGFubmVsX3ZlcnNpb24iOiIiLCJpcCI6IjIxNy4yMTcuMjQ2LjQiLCJpcHY2IjoiIiwiY29tbWVudGFibGUiOjEsInVzZXJfbmFtZSI6Ikp1ZGl0aCIsImFkdWx0X2FjY2VzcyI6MSwiYWdlbnRfaWQiOjAsImNvdW50cnlfY29kZSI6Ik5MIiwicGF5X21vZGUiOjAsImV4cCI6MTc2MzEyMzA1OH0.UeTLNP4cCyrAb3eyIeA_kprjF1Rj6dlwTLW_qL8MKjQ"

clients = set()
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def fc2_listener():
    def on_message(ws, message):
        # Рассылаем всем подключённым клиентам
        for client in list(clients):
            asyncio.run_coroutine_threadsafe(client.send(message), loop)

    def on_open(ws):
        print("🚀 Подключено к FC2")
        ws.send(json.dumps({
            "name": "get_comment",
            "arguments": {
                "last_comment_index": -1
            }
        }))

    def on_error(ws, error):
        print("❌ Ошибка FC2:", error)

    def on_close(ws, code, msg):
        print("🔌 FC2 соединение закрыто")

    ws = websocket.WebSocketApp(
        FC2_WS_URL,
        on_message=on_message,
        on_open=on_open,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

async def handler(websocket, path):
    print("🧩 Клиент подключился")
    clients.add(websocket)
    try:
        async for _ in websocket:
            pass
    finally:
        clients.remove(websocket)
        print("❎ Клиент отключился")

async def start_proxy():
    threading.Thread(target=fc2_listener, daemon=True).start()
    server = await websockets.serve(handler, "0.0.0.0", 8080)  # слушаем на всех интерфейсах
    print("🛡️ Прокси запущен на ws://0.0.0.0:8080 (или wss://arinairina.duckdns.org/ws/)")
    await server.wait_closed()

if __name__ == "__main__":
    loop.run_until_complete(start_proxy())
    loop.run_forever()
