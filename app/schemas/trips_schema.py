from datetime import datetime, timedelta
from typing import List, Optional, Dict
from app.schemas.forms_schema import TripType
from pydantic import BaseModel, field_validator
from enum import Enum

# Modified classes for MongoDB compatibility


class LatLong(BaseModel):
    latitude: float
    longitude: float


class PlaceInfo(BaseModel):
    id: Optional[str] = None
    name: str
    location: LatLong
    types: List[str]
    photos: Optional[List] = None
    accessibility_options: Optional[Dict] = None
    opening_hours: Optional[Dict] = None
    price_range: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    international_phone_number: Optional[str] = None
    national_phone_number: Optional[str] = None
    allows_dogs: Optional[bool] = None
    good_for_children: Optional[bool] = None
    good_for_groups: Optional[bool] = None


class Activity(BaseModel):
    id: int
    place: PlaceInfo
    start_time: datetime | str
    end_time: datetime | str
    activity_type: str
    duration: int  # in minutes


class Route(BaseModel):
    polylineEncoded: str
    duration: int
    distance: int


class Day(BaseModel):
    date: datetime | str
    morning_activities: List[Activity] = []
    afternoon_activities: List[Activity] = []
    routes: Optional[List[Route]] = None


class Trip(BaseModel):
    trip_type:str
    start_date: datetime | str
    end_date: datetime | str
    days: List[Day] = []
    name: str


class TripSaveRequest(BaseModel):
    id: str
    itinerary: Trip
