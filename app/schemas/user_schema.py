from pydantic import BaseModel, ConfigDict
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

    model_config = ConfigDict(from_attributes=True)