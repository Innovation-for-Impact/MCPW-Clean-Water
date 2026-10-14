from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import auth, events, health, incidents, lookup, webhooks

app = FastAPI(
    title="MCPW Clean Water API",
    description="Backend API for the Macomb County Public Works Clean Water incident response system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend dev server
        "http://localhost:5173",  # Vite dev server
    ],
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
