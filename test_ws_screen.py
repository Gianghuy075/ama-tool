import asyncio
import json
import websockets
import os

async def test():
    async with websockets.connect('ws://127.0.0.1:22222/') as ws:
        await ws.send(json.dumps({'action': 'list'}))
        devices = json.loads(await ws.recv())['data']
        if devices:
            serial = devices[0]['serial']
            print('Device serial:', serial)
            save_dir = os.path.abspath('logs')
            print('Save dir:', save_dir)
            
            # test lowercase "screen"
            payload = {
                'action': 'screen', 
                'devices': serial,
                'data': {
                    'savePath': save_dir
                }
            }
            print('Sending:', payload)
            await ws.send(json.dumps(payload))
            resp = json.loads(await ws.recv())
            
            with open('screen_response_lowercase.json', 'w', encoding='utf-8') as f:
                json.dump(resp, f, indent=4, ensure_ascii=False)
            print('Lowercase result - Code:', resp.get('code'), 'Message:', resp.get('message'))

            # test uppercase "Screen"
            payload['action'] = 'Screen'
            print('Sending:', payload)
            await ws.send(json.dumps(payload))
            resp = json.loads(await ws.recv())
            
            with open('screen_response_uppercase.json', 'w', encoding='utf-8') as f:
                json.dump(resp, f, indent=4, ensure_ascii=False)
            print('Uppercase result - Code:', resp.get('code'), 'Message:', resp.get('message'))

asyncio.run(test())
