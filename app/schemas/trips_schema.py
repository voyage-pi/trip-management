from pydantic import BaseModel
from typing import List

class Trip(BaseModel):
    id: int
    image: str
    days: int
    people: int
    destinations: int
    name: str
    date: str
    status: str

class TripList(BaseModel):
    trips: List[Trip]
