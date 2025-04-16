from app.database.CacheClient import RedisClient 
from app.schemas.response import ResponseBody
from fastapi import APIRouter,status
from app.schemas.trips_schema import Trip,TripSaveRequest
from app.schemas.forms_schema import Form
from app.database.MongoClient import DBClient
import requests as request
import json
from pydantic import ValidationError
from bson import ObjectId
from typing import List
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/api",
    tags=["trips"],
    responses={404: {"description": "Trips not found"}},
)


# create global redis instance 
redis_client = RedisClient()
# Mock trips data
@router.post("/trips")
async def trip_creation(forms: Form):
    try:
        # generate document Id for itinerary document and cache
        documentID=ObjectId()
        trip_type = forms.tripType
        display_name = forms.display_name
        questionnaire = []
        for user_id, user_questions in forms.questions.items():
            for q in user_questions:
                questionnaire.append(
                    {"question_id": q.question_id, "value": q.value, "type": "scale"}
                )

        delta = timedelta(days=forms.duration)
        requestBody = {
            "questionnaire": questionnaire,
            "start_date": forms.dateStart,
            "end_date": forms.dateStart + delta,
            "budget": forms.budget,
        }

        data_type = forms.data_type.model_dump()
        requestBody["data"]=data_type
        requestBody["tripType"]=trip_type.value
        # Converter datas para string ISO
        requestBody["start_date"] = requestBody["start_date"].isoformat()
        requestBody["end_date"] = requestBody["end_date"].isoformat()

        # Depuração
        print("Sending to recommendations service:", json.dumps(requestBody))
        response = request.post(
            "http://recommendations:8080/trip", json=requestBody, timeout=40
        )
        if response.status_code != 200:
            print(f"Error from recommendations service: {response.text}")
            return ResponseBody(
                {"error": response.text}, "Error from recommendations service", status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        r=response.json()["itinerary"]
        itinerary = r
        await redis_client.set(str(documentID),json.dumps(itinerary),expire=3600)
        return ResponseBody({"tripId":str(documentID),"itinerary": itinerary,"name":display_name}, "Trips created")
    except Exception as e:
        print(f"Error making request to recommendations service: {str(e)}")
        return ResponseBody(
            {"error": str(e)}, "Error connecting to recommendations service", status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@router.post("/save")
async def save_trip(trip:TripSaveRequest):
    client = DBClient()
    try:
        result=client.post_trip([trip.itinerary],[trip.id])
        if len(result)!=0:
            return ResponseBody({"trip_id":trip.id}, "Trips saved")
        raise Exception
    except Exception as e:
        print(f"Error inserting trip into the database: {str(e)}")
        return ResponseBody(
            {"error": str(e)}, "", status.HTTP_500_INTERNAL_SERVER_ERROR 
        )

@router.get("/trips/{id}")
async def get_trip(id: str):
    client = DBClient()
    try:
        itinerary=await redis_client.get(str(id))
        if itinerary is not None:
            return ResponseBody({"trips": json.loads(itinerary)})
        result = client.get_trip_by_id(id)
        if not isinstance(result,str) and result is not None:
            return ResponseBody({"trips":  result.model_dump() if isinstance(result,Trip) else result})
        return ResponseBody({}, "No trip found for this id.",status.HTTP_204_NO_CONTENT)
    except Exception as e :
        print(f"Error inserting trip into the database: {str(e)}")
        return ResponseBody(
            {"error": str(e)}, "Error while fetching for the trip by id.", status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.put("/trip/{id}")
async def update_trip(id: str, trip: Trip):
    client = DBClient()
    try:
        if client.put_trip_by_doc_id(id, trip):
            return ResponseBody({"updated": True}, "Trip Updated with sucess!", status.HTTP_201_CREATED)
        return ResponseBody({}, "No trip updated!", status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return ResponseBody({"error": e}, "Unexpected error!", status.HTTP_400_BAD_REQUEST )
