import asyncio
import logging
from typing import Optional

from src.processing import PacketParser

logger = logging.getLogger("ingestion")

class IngestionServer:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server: Optional[asyncio.AbstractServer] = None

    async def start(self):
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(f"Ingestion Server running on {self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        parser = PacketParser()
        addr = writer.get_extra_info('peername')
        logger.info(f"Connected: {addr}")

        try:
            while True:
                # [Defense] Backpressure: Throttle reading if internal buffer exceeds 1MB
                if len(parser.buffer) > 1 * 1024 * 1024:
                    logger.debug(f"Backpressure active for {addr}. Throttling...")
                    await asyncio.sleep(0.1)  # Pause reading slightly

                # [Defense] Safety Valve: Absolute Max Buffer Size 10MB
                if len(parser.buffer) > 10 * 1024 * 1024:
                    logger.warning(f"Safety Valve Triggered: Dropping {addr} (Buffer > 10MB)")
                    break

                # [Defense] Timeout: Disconnect if no data received for 30 seconds
                try:
                    data = await asyncio.wait_for(reader.read(4096), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Connection Timed Out: {addr} (Idle > 30s)")
                    break

                if not data:
                    break

                # Parse and Process
                packets = parser.parse(data)
                for packet in packets:
                    # In a real app, we would dispatch this to a processor
                    # logger.debug(f"Received Packet: {len(packet)} bytes")
                    pass

        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            logger.info(f"Disconnected: {addr}")
            writer.close()
            await writer.wait_closed()
