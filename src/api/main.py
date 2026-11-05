import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import RequestLoggingMiddleware
from src.api.routes import (
    auth,
    contacts,
    events,
    health,
    incidents,
    layers,
    lookup,
    rules,
    webhooks,
)
from src.logging_config import setup_logging

setup_logging()

app = FastAPI(
    title="MCPW Clean Water API",
    description="Backend API for the Macomb County Public Works Clean Water incident response system.",
    version="1.0.0",
)

_default_origins = ["http://localhost:3000", "http://localhost:5173"]
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()] or _default_origins

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, tags=["Auth"])
app.include_router(lookup.router, tags=["Lookup"])
app.include_router(incidents.router, tags=["Incidents"])
app.include_router(events.router, tags=["Events"])
app.include_router(webhooks.router, tags=["Webhooks"])
app.include_router(contacts.router, tags=["Contacts"])
app.include_router(rules.router, tags=["Rules"])
app.include_router(layers.router, tags=["Layers"])
