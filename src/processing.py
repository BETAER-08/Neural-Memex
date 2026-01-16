import struct
import logging
from typing import List

logger = logging.getLogger("processing")

# [Protocol] Constants
MAGIC_BYTE = b'\xBE\xEF'  # [Defense] Magic Byte 0xBEEF
HEADER_SIZE = 6  # 2 bytes Magic + 4 bytes Length

class PacketParser:
    def __init__(self):
        self.buffer = bytearray()

    def parse(self, data: bytes) -> List[bytes]:
        """
        Parses incoming raw bytes into discrete packets using Magic Byte header.
        Implements Self-Healing to recover from stream desync or corruption.
        """
        self.buffer.extend(data)
        packets = []

        while True:
            # [Protocol] Self-Healing: Search for the next Magic Byte
            magic_index = self.buffer.find(MAGIC_BYTE)
            
            if magic_index == -1:
                # Magic byte not found. 
                # Keep the last byte if it matches the first byte of MAGIC (partial match)
                # otherwise clear buffer to prevent memory leak on garbage stream.
                if len(self.buffer) > 0 and self.buffer[-1] == MAGIC_BYTE[0]:
                    self.buffer = self.buffer[-1:]
                else:
                    self.buffer.clear()
                break
            
            # [Protocol] Self-Healing: Discard corrupt data/garbage before the Magic Byte
            if magic_index > 0:
                logger.warning(f"Discarding {magic_index} bytes of garbage data.")
                self.buffer = self.buffer[magic_index:]
            
            # Check if we have enough data for a header
            if len(self.buffer) < HEADER_SIZE:
                break
                
            # Parse Payload Length
            # Structure: [Magic:2][Length:4][Payload:...]
            _, length = struct.unpack('>2sI', self.buffer[:HEADER_SIZE])
            
            # Check for sanity/max packet size if needed (optional defense)
            # if length > MAX_PACKET_SIZE: ...
            
            # Check if we have the full packet
            total_size = HEADER_SIZE + length
            if len(self.buffer) < total_size:
                # Wait for more data
                break
                
            # Extract Payload
            payload = self.buffer[HEADER_SIZE:total_size]
            packets.append(bytes(payload))
            
            # Move buffer forward
            self.buffer = self.buffer[total_size:]
            
        return packets
