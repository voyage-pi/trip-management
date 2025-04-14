from datetime import datetime, timedelta
from typing import List,Dict,Any, Optional
from pydantic import BaseModel
from enum import Enum


class QuestionType(Enum):
    SCALE="scale"
    SELECT="select"

class Question(BaseModel):
    question_id:int
    value:Any
    type:QuestionType
    class Config:
        use_enum_values = True

class TripType(Enum):
    PLACE= "place"
    ROAD = "road"
    ZONE = "zone"

class LatLong(BaseModel):
    latitude:float
    longitude:float

class Road(BaseModel):
    origin:LatLong
    destination:LatLong

class Place(BaseModel):
    coordinates:LatLong

class Zone(BaseModel):
    center:LatLong
    radius:int

class Form(BaseModel):
    budget:float
    dateStart:datetime
    duration:int # duration in days
    tripType:TripType
    data_type: Optional[Place]| Optional[Zone]| Optional[Road]
    users:List[str]
    questions:Dict[str,List[Question]]


