from fastapi import Request
from slowapi import Limiter


def get_client_address(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For when behind a reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=get_client_address)
