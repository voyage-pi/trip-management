from datetime import datetime 
from typing import List, Optional, Dict
from pydantic import BaseModel, root_validator

class LatLong(BaseModel):
    latitude: float
    longitude: float

class PriceRange(BaseModel):
    start_price:float
    end_price:float
    currency:str

class PlaceInfo(BaseModel):
    id: Optional[str] = None
    name: str
    location: LatLong
    types: List[str]
    photos: Optional[List] = None
    accessibility_options: Optional[Dict] = None
    opening_hours: Optional[Dict] = None
    price_range: Optional[PriceRange] = None
    price_level: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    international_phone_number: Optional[str] = None
    national_phone_number: Optional[str] = None
    allows_dogs: Optional[bool] = None
    good_for_children: Optional[bool] = None
    good_for_groups: Optional[bool] = None

    @root_validator(pre=True)
    def handle_place_id_field(cls, values):
        """Handle both 'id' and 'place_id' fields from different sources"""
        if isinstance(values, dict):
            # If id is None or missing, try to use place_id
            if values.get('id') is None and 'place_id' in values:
                values['id'] = values['place_id']
        return values
    
    class Config:
        extra = "ignore"  # Ignore extra fields like 'place_id'

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
    start_date: datetime | str  = None
    end_date: datetime | str
    days: List[Day] = []
    name: str
    trip_type: Optional[str]
    country: str | None = None
    city: str | None = None
    prince_range: Optional[PriceRange] = None
    is_group: bool
    # Original location data for regeneration
    original_place_data: Optional[Dict] = None  # Store the original place/zone/road data
    center_coordinates: Optional[LatLong] = None  # For zone trips
    place_coordinates: Optional[LatLong] = None   # For place trips
    origin_coordinates: Optional[LatLong] = None  # For road trips
    destination_coordinates: Optional[LatLong] = None  # For road trips

class Stop(BaseModel):
    place: PlaceInfo
    index: int
    id: str

class RoadItinerary(BaseModel):
    name: str
    stops: List[Stop]
    routes: List[Route]
    suggestions: List[PlaceInfo]
    trip_type: Optional[str]
    country: str | None = None
    city: str | None = None
    is_group: bool
    # Original location data for regeneration
    original_place_data: Optional[Dict] = None  # Store the original road data
    origin_coordinates: Optional[LatLong] = None
    destination_coordinates: Optional[LatLong] = None

class TripResponse(BaseModel):
    itinerary: Trip | RoadItinerary
    tripId: str
    preference_id:Optional[int]=None

class TripSaveRequest(BaseModel):
    id: str
    itinerary: Trip | RoadItinerary
    trip_type: str
    is_group: bool
    preference_id: Optional[int] = None

