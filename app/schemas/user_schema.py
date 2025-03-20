from pydantic import BaseModel
from typing import List

class Stats(BaseModel):
    trips: int
    friends: int
    saved: int
    countries: int

class User(BaseModel):
    name: str
    tag: str
    image: str
    stats: Stats
    class Config:
        orm_mode = True
