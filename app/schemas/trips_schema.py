from pydantic import BaseModel, ConfigDict
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
    user_tag: str

    model_config = ConfigDict(from_attributes=True)


class TripList(BaseModel):
    trips: List[Trip]
