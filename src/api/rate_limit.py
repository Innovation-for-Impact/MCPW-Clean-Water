import os

from fastapi import Request
from slowapi import Limiter


def get_client_address(request: Request) -> str:
    """Extract client IP for rate limiting.

    Only trusts X-Forwarded-For when TRUSTED_PROXY=true is set,
    preventing header spoofing in direct-connection deployments.
    """
    if os.environ.get("TRUSTED_PROXY", "").lower() == "true":
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=get_client_address)
