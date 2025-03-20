from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import base_router
from app.routes import user_router
from app.routes import trip_router

app = FastAPI()


app.include_router(base_router.router)
app.include_router(user_router.router)
app.include_router(trip_router.router)

origins = [
    "http://localhost:8080",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
