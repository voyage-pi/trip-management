from datetime import datetime, timedelta
from typing import List,Dict
from pydantic import BaseModel
from enum import Enum


class Question(BaseModel):
    id:str
    value:int
    typeQuestion:str

class TripType(Enum):
    PLACE= "place"
    ROAD = "road"
    ZONE = "zone"

class Form(BaseModel):
    budget:int
    dateStart:datetime
    duration:int # duration in days
    tripType:TripType
    people:List[str]
    user_questions:Dict[str,List[Question]]


