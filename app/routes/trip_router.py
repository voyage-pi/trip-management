from app.database import MongoClient
from app.schemas.response import ResponseBody
from fastapi import APIRouter
from app.schemas.trips_schema import Trip
from app.schemas.forms_schema import Form, TripType
from app.database.MongoClient import DBClient
import requests as request
import json
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/api",
    tags=["trips"],
    responses={404: {"description": "Trips not found"}},
)


# Mock trips data
@router.post("/trips", response_model=ResponseBody)
async def trip_creation(forms: Form):
    try:
        trip_type = forms.tripType

        questionnaire = []
        for user_id, user_questions in forms.questions.items():
            for q in user_questions:
                questionnaire.append(
                    {"question_id": q.question_id, "value": q.value, "type": "scale"}
                )

        delta = timedelta(days=forms.duration)
        requestBody = {
            "questionnaire": questionnaire,
            "place_name": forms.place.place_name,
            "start_date": forms.dateStart,
            "end_date": forms.dateStart + delta,
            "budget": forms.budget,
        }

        data_type = forms.data_type

        if TripType(trip_type) == TripType.PLACE:
            coordinates = data_type.coordinates
            requestBody["coordinates"] = coordinates.model_dump()
        elif TripType(trip_type) == TripType.ROAD:
            origin = data_type.origin
            destination = data_type.destination
        elif TripType(trip_type) == TripType.ZONE:
            radius = data_type.radius
            center = data_type.center.model_dump()
            requestBody["radius"] = radius
            requestBody["center"] = center

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
                {"error": response.text}, "Error from recommendations service", 500
            )
        itinerary = response.json()
        return ResponseBody({"itinerary": itinerary}, "Trips created")
    except Exception as e:
        print(f"Error making request to recommendations service: {str(e)}")
        return ResponseBody(
            {"error": str(e)}, "Error connecting to recommendations service", 500
        )


# Gets all trips of a user by user id
@router.get("/users/{user_id}/trips", response_model=ResponseBody)
async def get_user_trips(user_id: str):
    client = DBClient()
    result = client.get_trip_by_user_id(user_id)
    if len(result) == 0:
        return ResponseBody(
            {}, "Either the user doesn't exist or didn't create a trip yet", 204
        )
    return ResponseBody({"trips": result}, "Trips retrieved with success!", 200)


# Get a single trip by its ID
@router.get("/trips/{trip_id}", response_model=ResponseBody)
async def get_trip_by_id(trip_id: str):
    client = DBClient()
    result = client.get_trip_by_id(trip_id)
    if not result:
        return ResponseBody(
            {}, "Trip not found", 404
        )
    return ResponseBody({"itinerary": result}, "Trip retrieved with success!", 200)


@router.put("/trip/{id}", response_model=ResponseBody)
async def update_trip(id: str, trip: Trip):
    client = DBClient()
    try:
        if client.put_trip_by_doc_id(id, trip):
            return ResponseBody({"updated": True}, "Trip Updated with sucess!", 201)
        return ResponseBody({}, "No trip updated!", 204)
    except Exception as e:
        return ResponseBody({"error": e}, "Unexpected error!", 400)

@router.get("/trips/all", response_model=ResponseBody)
async def get_all_trips():
    client = DBClient()
    result = client.get_all_trips()
    return ResponseBody({"trips": result}, "Trips retrieved with success!", 200)

# Delete Places from a certain day on a certain trip
# Get new trip for a slot from a certain trip
# Update route between places for a certain day
