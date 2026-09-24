"""InevioNet WebSocket client and server."""
import asyncio
import time
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

try:
    import websockets
    from websockets.client import connect as ws_connect
    from websockets.server import serve as ws_serve
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    ws_connect = None
    ws_serve = None
    ConnectionClosed = Exception

from ..core.logger import get_logger

logger = get_logger("inevionet.network.websocket")


class WSClient:
    def __init__(self, uri, timeout=10.0, ping_interval=20.0, max_size=10*1024*1024, extra_headers=None):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not installed. Run: pip install websockets")
        self.uri = uri
        self.timeout = timeout
        self.ping_interval = ping_interval
        self.max_size = max_size
        self.extra_headers = extra_headers or {}
        self._ws = None
        self._loop = None
        self._connected = False
        self._bytes_sent = 0
        self._bytes_received = 0

    def connect(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._ws = self._loop.run_until_complete(
                asyncio.wait_for(
                    ws_connect(self.uri, ping_interval=self.ping_interval,
                               max_size=self.max_size,
                               extra_headers=self.extra_headers),
                    timeout=self.timeout))
            self._connected = True
            logger.info(f"WebSocket connected: {self.uri}")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"WebSocket timeout: {self.uri}")
            return False
        except Exception as e:
            logger.error(f"WebSocket connect error: {e}")
            return False

    def send(self, data):
        if not self._connected or not self._ws:
            return False
        try:
            self._loop.run_until_complete(
                asyncio.wait_for(self._ws.send(data), timeout=self.timeout))
            self._bytes_sent += len(data)
            return True
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            return False

    def send_text(self, text):
        return self.send(text.encode("utf-8"))

    def recv(self):
        if not self._connected or not self._ws:
            return None
        try:
            result = self._loop.run_until_complete(
                asyncio.wait_for(self._ws.recv(), timeout=self.timeout))
            if isinstance(result, str):
                result = result.encode("utf-8")
            self._bytes_received += len(result)
            return result
        except asyncio.TimeoutError:
            return None
        except ConnectionClosed as e:
            self._connected = False
            return None
        except Exception as e:
            logger.error(f"WebSocket recv error: {e}")
            return None

    def recv_text(self):
        data = self.recv()
        return data.decode("utf-8") if data else None

    def request(self, data):
        if self.send(data):
            return self.recv()
        return None

    def close(self):
        if self._ws and self._connected:
            try:
                self._loop.run_until_complete(
                    asyncio.wait_for(self._ws.close(), timeout=3.0))
            except Exception:
                pass
        if self._loop:
            try:
                self._loop.close()
            except Exception:
                pass
        self._ws = None
        self._loop = None
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    @property
    def bytes_sent(self):
        return self._bytes_sent

    @property
    def bytes_received(self):
        return self._bytes_received

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


class WSServer:
    def __init__(self, host="0.0.0.0", port=8765, on_message=None,
                 on_connect=None, on_disconnect=None, max_size=10*1024*1024):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not installed")
        self.host = host
        self.port = port
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.max_size = max_size
        self._clients = []
        self._running = False
        self._loop = None
        self._thread = None

    async def _handler(self, websocket, path=None):
        client_id = f"client_{len(self._clients)}_{id(websocket)}"
        self._clients.append(websocket)
        logger.info(f"WebSocket client connected: {client_id}")
        if self.on_connect:
            try:
                if asyncio.iscoroutinefunction(self.on_connect):
                    await self.on_connect(client_id)
                else:
                    self.on_connect(client_id)
            except Exception as e:
                logger.error(f"on_connect error: {e}")
        try:
            async for message in websocket:
                if isinstance(message, str):
                    message = message.encode("utf-8")
                if self.on_message:
                    try:
                        if asyncio.iscoroutinefunction(self.on_message):
                            response = await self.on_message(client_id, message)
                        else:
                            response = self.on_message(client_id, message)
                        if response:
                            if isinstance(response, str):
                                await websocket.send(response)
                            else:
                                await websocket.send(response)
                    except Exception as e:
                        logger.error(f"on_message error: {e}")
        except Exception as e:
            logger.debug(f"WebSocket client {client_id} disconnected: {e}")
        finally:
            if websocket in self._clients:
                self._clients.remove(websocket)
            if self.on_disconnect:
                try:
                    if asyncio.iscoroutinefunction(self.on_disconnect):
                        await self.on_disconnect(client_id)
                    else:
                        self.on_disconnect(client_id)
                except Exception:
                    pass

    def start(self, blocking=True):
        import threading
        async def _serve():
            async with ws_serve(self._handler, self.host, self.port, max_size=self.max_size):
                self._running = True
                logger.info(f"WebSocket server on {self.host}:{self.port}")
                await asyncio.Future()
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        if blocking:
            try:
                self._loop.run_until_complete(_serve())
            except KeyboardInterrupt:
                self.stop()
        else:
            self._thread = threading.Thread(
                target=self._loop.run_until_complete, args=(_serve(),), daemon=True)
            self._thread.start()

    def broadcast(self, data):
        if not self._clients or not self._loop:
            return 0
        try:
            async def _broadcast():
                await asyncio.gather(*[c.send(data) for c in self._clients], return_exceptions=True)
            self._loop.run_until_complete(_broadcast())
            return len(self._clients)
        except Exception:
            return 0

    def stop(self):
        self._running = False
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.stop()
            except Exception:
                pass

    @property
    def client_count(self):
        return len(self._clients)

    def __enter__(self):
        self.start(blocking=False)
        return self

    def __exit__(self, *args):
        self.stop()


if __name__ == "__main__":
    if not WEBSOCKETS_AVAILABLE:
        print("Install websockets: pip install websockets")
        sys.exit(1)
    import socket, sys
    print("Testing WebSocket...")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    received = []
    def on_message(client_id, message):
        received.append(message)
        return b"ECHO: " + message

    server = WSServer(host="127.0.0.1", port=port, on_message=on_message)
    server.start(blocking=False)
    time.sleep(0.5)

    client = WSClient(f"ws://127.0.0.1:{port}")
    if client.connect():
        test = b"Hello, WebSocket!"
        if client.send(test):
            response = client.recv()
            if response:
                print(f"Echo: {response}")
        client.close()
    server.stop()
    print("WebSocket module OK")
