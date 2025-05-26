from typing import List,Dict,Union,Literal,Optional
from app.schemas.trips_schema import PlaceInfo 
from pydantic import BaseModel,Field
from enum import Enum


class QuestionType(str, Enum):
    SCALE = "scale"
    SELECT = "select"


class Question(BaseModel):
    question_id: int
    value: Optional[int]
    type: QuestionType

    class Config:
        use_enum_values = True

class TripType(Enum):
    PLACE = "place"
    ROAD = "road"
    ZONE = "zone"


class LatLong(BaseModel):
    latitude: float
    longitude: float

class Road(BaseModel):
    type: Literal["road"] = "road"  # Discriminator field
    origin:PlaceInfo 
    destination:PlaceInfo 
    polylines: str

class Place(BaseModel):
    type: Literal["place"] = "place"  # Discriminator field
    coordinates: LatLong
    place_name: str
    place_id: Optional[str] = None

class Zone(BaseModel):
    type: Literal["zone"] = "zone"  # Discriminator field
    center: LatLong
    radius: int

class Preferences(BaseModel):
    questions:List[Question]
    preferencesName:Optional[str] = None

class Form(BaseModel):
    budget: float
    startDate: str
    duration: int = 3
    preferences: Preferences
    must_visit_places: List[PlaceInfo] = []
    keywords: List[str] = []
    tripType: TripType
    display_name: str
    country: str | None = None
    city: str | None = None
    data_type: Union[Zone, Place, Road] = Field(discriminator="type")
    is_group: bool
    preference_id: Optional[int] = None
