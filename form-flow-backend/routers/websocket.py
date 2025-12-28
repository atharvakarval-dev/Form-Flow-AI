from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time communication.
    
    Accepts connections from the browser extension and clients.
    Handles messages for voice processing, status updates, etc.
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted: {websocket.client}")
    
    try:
        while True:
            # Receive message (text or bytes)
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            
            # Echo back for now (or implement message handling logic)
            # You can dispatch to conversation agent here
            await websocket.send_text(f"Message received: {data}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass
