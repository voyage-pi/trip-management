from datetime import datetime, timedelta
from typing import TypedDict,List,Tuple

# Modified classes for MongoDB compatibility
class Place(TypedDict):
    placeId: str
    Location: Tuple[str, str]
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
    people: int

class TripList(TypedDict):
    trips: List[Trip]
