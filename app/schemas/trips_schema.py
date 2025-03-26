from datetime import datetime, timedelta
from typing import TypedDict,List,Tuple
from enum import Enum
# Modified classes for MongoDB compatibility
class State(Enum):
    DRAFTED ="drafted"
    INCOMING="incoming"
    COMPLETED="completed"

class Place(TypedDict):
    placeId: str
    location: Tuple[str, str]
    start_time: datetime
    end_time: datetime

class Route(TypedDict):
    polylines: List[str]
    duration: datetime

class Day(TypedDict):
    template_type: str
    places: List[Place]
    routes: List[Route]

class Trip(TypedDict):
    image: str
    days: List[Day]
    state:str
    people: List[str]

