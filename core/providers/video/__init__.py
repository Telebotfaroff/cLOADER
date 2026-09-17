"""Video-host providers.

Concrete video hosts are intentionally added only after their current upload
APIs are verified. This prevents silently treating incompatible hosts as if
they shared one protocol.
"""

from .generic import GenericVideoProvider

__all__ = ["GenericVideoProvider"]
