import hashlib
import hmac

from .errors import InvalidSignatureError


SIGNATURE_HEADER = "x-plane-signature"


def verify_signature(raw_body: bytes, provided_signature: str, secret: str) -> None:
    """Validate webhook signature using HMAC-SHA256."""
    if not provided_signature:
        raise InvalidSignatureError("missing signature header")

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    # Plane docs show the signature header as a plain hex digest, while some
    # tools may send "sha256=<hex>".
    received = provided_signature
    if provided_signature.startswith("sha256="):
        received = provided_signature.split("=", 1)[1]

    if not hmac.compare_digest(expected, received):
        raise InvalidSignatureError("signature mismatch")
