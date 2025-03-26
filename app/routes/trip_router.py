from app.database import MongoClient
from app.schemas.response import ResponseBody
from fastapi import APIRouter
from app.schemas.trips_schema import Trip,State 
from app.schemas.forms_schema import Form
from app.database.MongoClient import DBClient
from fastapi import HTTPException
import json
from datetime import datetime,timedelta

router = APIRouter(
    prefix="/api",
    tags=["trips"],
    responses={404: {"description": "Trips not found"}},
)

# Mock trips data
@router.post("/trips",response_model=ResponseBody)
async def trip_creation(forms:Form):
    people=forms.people 
    # here the request has to be made to the recommendation system since is what is going to make the trip structure
    trip1: Trip = {
        "image": "https://example.com/image1.jpg",
        "days": [
            {
                "template_type": "leisure",
                "places": [
                    {
                        "placeId": "place123",
                        "location": ("Lisbon", "Portugal"),
                        "start_time": datetime.now(),
                        "end_time": datetime.now() + timedelta(hours=2),
                    },
                    {
                        "placeId": "place456",
                        "location": ("Porto", "Portugal"),
                        "start_time": datetime.now() + timedelta(hours=3),
                        "end_time": datetime.now() + timedelta(hours=5),
                    },
                ],
                "routes": [
                    {
                        "polylines": ["abc123", "def456"],
                        "duration": datetime.now() + timedelta(hours=1, minutes=30),
                    }
                ],
            }
        ],
        "state":"incoming",
        "people": ["user1", "user2"],
    }

    trip2: Trip = {
        "image": "https://example.com/image2.jpg",
        "days": [
            {
                "template_type": "business",
                "places": [
                    {
                        "placeId": "place789",
                        "location": ("Madrid", "Spain"),
                        "start_time": datetime.now() + timedelta(days=1),
                        "end_time": datetime.now() + timedelta(days=1, hours=4),
                    }
                ],
                "routes": [
                    {
                        "polylines": ["ghi789", "jkl012"],
                        "duration": datetime.now() + timedelta(hours=4),
                    }
                ],
            },
            {
                "template_type": "sightseeing",
                "places": [
                    {
                        "placeId": "place321",
                        "location": ("Barcelona", "Spain"),
                        "start_time": datetime.now() + timedelta(days=2),
                        "end_time": datetime.now() + timedelta(days=2, hours=3),
                    }
                ],
                "routes": [
                    {
                        "polylines": ["mno345", "pqr678"],
                        "duration": datetime.now() + timedelta(hours=2, minutes=15),
                    }
                ],
            },
        ],
        "state": "drafted",
        "people": ["user3", "user4", "user5"]
    }
    client=DBClient()
    ids=client.post_trip([trip1,trip2])
    return ResponseBody({"ids":ids},"Trips created")

#Gets all of an user by id
@router.get("/trips/{id}", response_model=ResponseBody)
async def get_trips(id: str):
    client= DBClient()
    result=client.get_trip_by_user_id(id)
    if len(result)==0:
        return ResponseBody({},"Either the user doens't exist or didn't create a trip yet",204)
    return ResponseBody({"trips":result}) 




