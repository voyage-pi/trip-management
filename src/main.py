from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import base_router

app = FastAPI()


app.include_router(base_router.router)

origins = [
    "http://localhost",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
