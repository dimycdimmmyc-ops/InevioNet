"""InevioNet Exceptions."""


class InevioException(Exception):
    def __init__(self, message="", code="INEVIO_ERROR", details=None, original=None):
        self.message = message
        self.code = code
        self.details = details or {}
        self.original = original
        full = f"[{code}] {message}"
        if original:
            full += f" (cause: {original})"
        super().__init__(full)

    def to_dict(self):
        return {"error": True, "code": self.code, "message": self.message,
                "details": self.details}


class CryptoError(InevioException):
    def __init__(self, message, original=None):
        super().__init__(message=message, code="CRYPTO_ERROR", original=original)


class KeyError(CryptoError):
    def __init__(self, message, original=None):
        super().__init__(message=message, original=original)
        self.code = "KEY_ERROR"


class EncryptionError(CryptoError):
    def __init__(self, message, original=None):
        super().__init__(message=message, original=original)
        self.code = "ENCRYPTION_ERROR"


class DecryptionError(CryptoError):
    def __init__(self, message, original=None):
        super().__init__(message=message, original=original)
        self.code = "DECRYPTION_ERROR"


class IntegrityError(CryptoError):
    def __init__(self, message, original=None):
        super().__init__(message=message, original=original)
        self.code = "INTEGRITY_ERROR"


class NetworkError(InevioException):
    def __init__(self, message, details=None, original=None):
        super().__init__(message=message, code="NETWORK_ERROR",
                         details=details, original=original)


class TimeoutError(NetworkError):
    def __init__(self, operation, timeout, original=None):
        super().__init__(f"Timeout in '{operation}' ({timeout}s)",
                         {"operation": operation, "timeout": timeout}, original)
        self.code = "TIMEOUT_ERROR"


class ConnectionError(NetworkError):
    def __init__(self, host, port, original=None):
        super().__init__(f"Connection failed to {host}:{port}",
                         {"host": host, "port": port}, original)
        self.code = "CONNECTION_ERROR"


class SteganographyError(InevioException):
    def __init__(self, message, details=None, original=None):
        super().__init__(message=message, code="STEGANOGRAPHY_ERROR",
                         details=details, original=original)


class DeliveryError(InevioException):
    def __init__(self, message, details=None, original=None):
        super().__init__(message=message, code="DELIVERY_ERROR",
                         details=details, original=original)


class ConfigurationError(InevioException):
    def __init__(self, message, details=None, original=None):
        super().__init__(message=message, code="CONFIGURATION_ERROR",
                         details=details, original=original)

class PacketCorruptedError(InevioException):
    """Ошибка повреждённого пакета."""
    def __init__(self, message="Packet corrupted", details=None, original=None):
        super().__init__(message=message, code="PACKET_CORRUPTED_ERROR",
                         details=details, original=original)

class PacketCorruptedError(InevioException):
    """Ошибка повреждённого пакета."""
    def __init__(self, message="Packet corrupted", details=None, original=None):
        super().__init__(message=message, code="PACKET_CORRUPTED_ERROR",
                         details=details, original=original)

class PayloadTooLargeError(SteganographyError):
    """Payload exceeds method limit."""
    def __init__(self, method, payload_size, max_size):
        super().__init__(
            message=f"Payload {payload_size}B > {max_size}B for {method}",
            details={"method": method, "payload_size": payload_size, "max_size": max_size})
        self.code = "PAYLOAD_TOO_LARGE_ERROR"


class EncodingError(SteganographyError):
    """Encoding error."""
    def __init__(self, method, original=None):
        super().__init__(message=f"Encoding error via {method}",
                         details={"method": method}, original=original)
        self.code = "ENCODING_ERROR"


class DecodingError(SteganographyError):
    """Decoding error."""
    def __init__(self, method, original=None):
        super().__init__(message=f"Decoding error via {method}",
                         details={"method": method}, original=original)
        self.code = "DECODING_ERROR"


class MaxRetriesExceededError(DeliveryError):
    """Max retries exceeded."""
    def __init__(self, packet_id, attempts):
        super().__init__(message=f"Packet {packet_id} not delivered after {attempts} attempts",
                         details={"packet_id": packet_id, "attempts": attempts})
        self.code = "MAX_RETRIES_EXCEEDED_ERROR"


class PacketExpiredError(DeliveryError):
    """Packet expired."""
    def __init__(self, packet_id, ttl):
        super().__init__(message=f"Packet {packet_id} expired (TTL={ttl})",
                         details={"packet_id": packet_id, "ttl": ttl})
        self.code = "PACKET_EXPIRED_ERROR"


class DNSResolutionError(NetworkError):
    """DNS resolution failed."""
    def __init__(self, hostname, original=None):
        super().__init__(message=f"Cannot resolve {hostname}",
                         details={"hostname": hostname}, original=original)
        self.code = "DNS_RESOLUTION_ERROR"


class RawSocketError(NetworkError):
    """Raw socket error."""
    def __init__(self, protocol, original=None):
        super().__init__(message=f"Raw socket {protocol} requires admin",
                         details={"protocol": protocol, "requires_root": True},
                         original=original)
        self.code = "RAW_SOCKET_ERROR"


class ConfigNotFoundError(ConfigurationError):
    """Config not found."""
    def __init__(self, path):
        super().__init__(message=f"Config not found: {path}", details={"path": path})
        self.code = "CONFIG_NOT_FOUND_ERROR"


class InvalidConfigError(ConfigurationError):
    """Invalid config."""
    def __init__(self, reason, original=None):
        super().__init__(message=f"Invalid config: {reason}",
                         details={"reason": reason}, original=original)
        self.code = "INVALID_CONFIG_ERROR"


class IndustrialProtocolError(InevioException):
    """Industrial protocol error."""
    def __init__(self, protocol, message, details=None, original=None):
        super().__init__(message=f"[{protocol}] {message}",
                         code="INDUSTRIAL_PROTOCOL_ERROR",
                         details={"protocol": protocol, **(details or {})},
                         original=original)
