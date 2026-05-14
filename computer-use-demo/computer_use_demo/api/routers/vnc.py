"""
WebSocket VNC proxy.

Bridges the browser ↔ x11vnc RFB WebSocket running on VNC_WS_URL
(defaults to ws://localhost:5900 via websockify).

This lets the frontend connect to a single FastAPI port rather than
needing a separate noVNC port exposed. The noVNC JS client is embedded
in the frontend and pointed at /sessions/{id}/vnc.

Note: noVNC on port 6080 remains available as a simpler alternative.
"""

import asyncio
import os

import websockets
import websockets.exceptions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/sessions", tags=["vnc"])

VNC_WS_URL = os.environ.get("VNC_WS_URL", "ws://localhost:5900")


@router.websocket("/{session_id}/vnc")
async def vnc_proxy(session_id: str, websocket: WebSocket) -> None:
    """
    Proxy WebSocket frames between the browser and the VNC server.
    Accepts the "binary" subprotocol required by the RFB protocol over WebSocket.
    """
    await websocket.accept(subprotocol="binary")

    try:
        async with websockets.connect(
            VNC_WS_URL,
            subprotocols=["binary"],
            max_size=10 * 1024 * 1024,  # 10 MB max frame
            open_timeout=5,
        ) as vnc_ws:

            async def browser_to_vnc() -> None:
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await vnc_ws.send(data)
                except (WebSocketDisconnect, Exception):
                    pass

            async def vnc_to_browser() -> None:
                try:
                    async for message in vnc_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except Exception:
                    pass

            tasks = [
                asyncio.create_task(browser_to_vnc()),
                asyncio.create_task(vnc_to_browser()),
            ]
            _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    except (websockets.exceptions.WebSocketException, OSError):
        # VNC server unreachable — close cleanly
        pass
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
