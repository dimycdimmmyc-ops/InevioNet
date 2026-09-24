"""InevioNet Capsule - embeddable library."""
from .capsule import InevioCapsule
from .embed import embed_inevionet, quick_send, quick_receive

__all__ = [
    "InevioCapsule",
    "embed_inevionet",
    "quick_send",
    "quick_receive",
]
