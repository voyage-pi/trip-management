from fastapi import APIRouter
from app.schemas.trips_schema import TripList, Trip
from fastapi import HTTPException
import json

with open("app/models/trips.json", "r") as f:
    trips = json.load(f)

with open("app/models/users.json", "r") as f:
    users = json.load(f)

router = APIRouter(
    prefix="/api",
    tags=["trips"],
    responses={404: {"description": "Trips not found"}},
)

# Mock trips data

@router.get("/trips/{user_tag}", response_model=TripList)
async def get_trips(user_tag: str):
    return TripList(trips=[trip for trip in trips["trips"] if trip["user_tag"] == user_tag])


@router.get("/trips/{user_tag}/{trip_id}", response_model=Trip)
async def get_trip(user_tag: str, trip_id: int):
    return Trip(trips=[trip for trip in trips["trips"] if trip["user_tag"] == user_tag and trip["id"] == trip_id])


@router.post("/trips/{user_tag}", response_model=Trip)
async def create_trip(user_tag: str, trip: Trip):
    # Ensure the user exists
    user = next((user for user in users["users"] if user["tag"] == user_tag), None)
    if user is None:
        raise HTTPException(status_code=400, detail=f"User tag '{user_tag}' not found")
    
    trip_data = trip.model_dump()
    trip_data["user_tag"] = user_tag
    trips["trips"].append(trip_data)
    
    # Save back to the JSON file
    with open('trips.json', 'w') as f:
        json.dump(trips, f, indent=2)
    
    return trip_data
