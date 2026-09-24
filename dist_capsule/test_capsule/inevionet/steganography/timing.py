"""Timing Channel Steganography - data in packet timing."""
import time
import struct
from typing import List, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.steganography.timing")


class TimingChannel:
    """
    Timing Channel - кодирование данных в интервалах между пакетами.
    """
    DEFAULT_BIT_DELAY = 0.05

    def __init__(self, bit_delay=0.05, tolerance=0.02):
        self.bit_delay = bit_delay
        self.tolerance = tolerance

    def encode_bytes_to_intervals(self, data: bytes) -> List[float]:
        """Преобразовать байты в список интервалов."""
        intervals = []
        for byte in data:
            for bit_pos in range(8):
                bit = (byte >> bit_pos) & 1
                interval = self.bit_delay if bit == 0 else self.bit_delay * 2
                intervals.append(interval)
        return intervals

    def decode_intervals_to_bytes(self, intervals: List[float]) -> bytes:
        """Восстановить байты из интервалов."""
        bits = []
        for interval in intervals:
            if abs(interval - self.bit_delay) < self.tolerance:
                bits.append(0)
            elif abs(interval - self.bit_delay * 2) < self.tolerance:
                bits.append(1)
            else:
                bits.append(0)
        result = bytearray()
        for i in range(0, len(bits), 8):
            chunk = bits[i:i+8]
            if len(chunk) < 8:
                break
            byte_val = 0
            for j, bit in enumerate(chunk):
                if bit:
                    byte_val |= (1 << j)
            result.append(byte_val)
        return bytes(result)

    def send_with_timing(self, data: bytes, send_func) -> bool:
        """Отправить данные с timing-кодированием."""
        try:
            intervals = self.encode_bytes_to_intervals(data)
            for interval in intervals:
                send_func(b"T")
                time.sleep(interval)
            return True
        except Exception as e:
            logger.error(f"Timing send error: {e}")
            return False

    def receive_with_timing(self, receive_func, num_bits: int,
                            timeout=1.0) -> Optional[bytes]:
        """Принять данные с timing-декодированием."""
        try:
            intervals = []
            last_time = time.time()
            for _ in range(num_bits):
                data = receive_func(timeout)
                if data is None:
                    return None
                now = time.time()
                interval = now - last_time
                intervals.append(interval)
                last_time = now
            return self.decode_intervals_to_bytes(intervals)
        except Exception as e:
            logger.error(f"Timing receive error: {e}")
            return None

    def __repr__(self):
        return f"TimingChannel(bit_delay={self.bit_delay})"


if __name__ == "__main__":
    print("Testing TimingChannel...")
    ch = TimingChannel(bit_delay=0.01)
    data = b"Hi"
    intervals = ch.encode_bytes_to_intervals(data)
    print(f"Encoded {len(data)} bytes into {len(intervals)} intervals")
    decoded = ch.decode_intervals_to_bytes(intervals)
    assert decoded == data, f"Decode failed: {decoded} != {data}"
    print(f"OK: round-trip works ({len(decoded)} bytes)")
    print("TimingChannel module OK")
