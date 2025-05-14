from datetime import datetime 
from typing import List,Dict,Any, Annotated,Union,Literal,Optional
from app.schemas.trips_schema import PlaceInfo
from pydantic import BaseModel,Field
from enum import Enum


class QuestionType(Enum):
    SCALE = "scale"
    SELECT = "select"


class Question(BaseModel):
    question_id: int
    value: Any
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

class Form(BaseModel):
    budget:float
    dateStart:datetime
    display_name:str
    duration:int # duration in days
    tripType:TripType
    data_type: Union[Road, Place, Zone] = Field(discriminator="type")  # This tells Pydantic to use the 'type' field
    users:List[str]
    questions:Dict[str,List[Question]]
    must_visit_places: Optional[List[Place]] = None
