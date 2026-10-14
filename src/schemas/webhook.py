import ipaddress
import socket
import urllib.parse

from pydantic import BaseModel, field_validator


class WebhookCreate(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urllib.parse.urlparse(v)
        if parsed.scheme not in ("https", "http"):
            raise ValueError("URL must use http or https scheme")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL must have a valid hostname")

        # Resolve hostname to IP(s) and check each — catches DNS names
        # pointing to private/internal addresses (e.g. metadata.google.internal)
        try:
            resolved = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            raise ValueError(f"Could not resolve hostname: {hostname}")

        for family, _type, _proto, _canonname, sockaddr in resolved:
            try:
                addr = ipaddress.ip_address(sockaddr[0])
                if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
                    raise ValueError(
                        "URL must not resolve to a private, loopback, reserved, or link-local address"
                    )
            except ValueError as e:
                if "does not appear to be" not in str(e):
                    raise
        return v


class WebhookResponse(BaseModel):
    id: int
    url: str
    active: bool
    created_at: str

    model_config = {"from_attributes": True}
