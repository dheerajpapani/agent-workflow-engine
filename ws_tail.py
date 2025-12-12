# ws_tail.py
import asyncio
import websockets
import json

async def tail(run_id):
    uri = f"ws://localhost:8080/ws/{run_id}"
    async with websockets.connect(uri) as ws:
        async for msg in ws:
            try:
                data = json.loads(msg)
            except Exception:
                print("RAW:", msg)
                continue
            print(data)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ws_tail.py <run_id>")
    else:
        asyncio.run(tail(sys.argv[1]))
