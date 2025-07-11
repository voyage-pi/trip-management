from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import base_router
from app.routes import trip_router
from app.routes import websocket_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(base_router.router)
app.include_router(trip_router.router)
app.include_router(websocket_router.router)
