import asyncio
import json
import websockets
import sys

async def test_ws():
    uri = "ws://127.0.0.1:22222/"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            payload = {"action": "list"}
            print(f"Sending payload: {payload}")
            await websocket.send(json.dumps(payload))
            
            print("Waiting for response...")
            response = await websocket.recv()
            print(f"Received response: {response}")
    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_ws())
