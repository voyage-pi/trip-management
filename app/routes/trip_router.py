from app.database import MongoClient
from app.schemas.response import ResponseBody
from fastapi import APIRouter
from app.schemas.trips_schema import Trip
from app.schemas.forms_schema import Form, TripType
from app.database.MongoClient import DBClient
import requests as request  
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
    trip_type=forms.tripType   
    place= forms.place
    questions = []
    for k,questions in forms.questions.items():
        questions.extend([q for q in questions ])
    delta = timedelta(days=forms.duration) 
    requestBody={
        "questionnaire":[q.dict() for q in questions],  # ou q.model_dump(),
        "start_date":forms.dateStart,
        "end_date":forms.dateStart + delta,
        "budget":forms.budget
    } 
    if TripType(trip_type)==TripType.PLACE:
        coordinates=place.coordinates 
        requestBody["coordinates"]=coordinates.dict()
        print(coordinates.dict())
    elif TripType(trip_type)==TripType.ROAD:
        origin=place.origin
        destination=place.destination
    elif TripType(trip_type)==TripType.ZONE:
        coordinates=place.coordinates 
    #generate the itinerary
    requestBody['start_date'] = requestBody['start_date'].isoformat()
    requestBody['end_date'] = requestBody['end_date'].isoformat()
    response=request.post("http://recommendations:8080/trip",json=requestBody)
    if response.status_code != 200:
        return ResponseBody({},"There was unexpected error",500)
    itinerary=response.json()
    return ResponseBody({"itinerary":itinerary},"Trips created")

#Gets all of an user by id
@router.get("/trips/{id}", response_model=ResponseBody)
async def get_trip(id: str):
    client= DBClient()
    result=client.get_trip_by_user_id(id)
    if len(result)==0:
        return ResponseBody({},"Either the user doens't exist or didn't create a trip yet",204)
    return ResponseBody({"trips":result}) 

@router.put("/trip/{id}",response_model=ResponseBody)
async def update_trip(id:str,trip:Trip):
    client=DBClient()
    try:
        if client.put_trip_by_doc_id(id,trip):
            return ResponseBody({"updated":True},"Trip Updated with sucess!",201)
        return ResponseBody({},"No trip updated!",204)
    except Exception as e: 
        return ResponseBody({"error":e},"Unexpected error!",400)


# Delete Places from a certain day on a certain trip
# Get new trip for a slot from a certain trip
# Update route between places for a certain day 
