from app.database.CacheClient import RedisClient
from app.schemas.response import ResponseBody
from fastapi import APIRouter, status, Request
from app.schemas.trips_schema import Trip, TripSaveRequest
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
    print(forms)
    try:
        # generate document Id for itinerary document and cache
        documentID = ObjectId()
        trip_type = forms.tripType
        display_name = forms.display_name
        questionnaire = []
        for user_id, user_questions in forms.questions.items():
            for q in user_questions:
                questionnaire.append(
                    {"question_id": q.question_id, "value": q.value, "type": "scale"}
                )

        delta = timedelta(days=forms.duration)

        must_visit_places = []

        if forms.must_visit_places:
            for place in forms.must_visit_places:
                must_visit_places.append(
                    {
                        "place_name": place.place_name,
                        "coordinates": {
                            "latitude": place.coordinates.latitude,
                            "longitude": place.coordinates.longitude,
                        },
                        "place_id": place.place_id,
                    }
                )

        requestBody = {
            "trip_id": str(documentID),
            "questionnaire": questionnaire,
            "start_date": forms.dateStart,
            "end_date": forms.dateStart + delta,
            "budget": forms.budget,
            # adding the display name as attribute to the trip
            "name": display_name,
            "must_visit_places": must_visit_places,
        }

        data_type = forms.data_type.model_dump()
        requestBody["data"] = data_type
        requestBody["tripType"] = trip_type.value
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
                {"error": response.text},
                "Error from recommendations service",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        itinerary = response.json()["itinerary"]
        # casting the dictionary to Trip BaseModel object
        itinerary = Trip(**itinerary)
        # casting the dictionary to Trip BaseModel object
        await redis_client.set(
            str(documentID), json.dumps(itinerary.model_dump()), expire=3600
        )

        return ResponseBody(
            {"tripId": str(documentID), "itinerary": itinerary.model_dump()},
            "Trips created",
        )
    except Exception as e:
        print(f"Error making request to recommendations service: {str(e)}")
        return ResponseBody(
            {"error": str(e)},
            "Error connecting to recommendations service",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post("/save")
async def save_trip(trip: TripSaveRequest, rq: Request):
    client = DBClient()
    try:
        already_exists = False
        try:
            print(trip.id)
            existing_trip = client.get_trip_by_id(str(trip.id))
            print("Existing trip:", existing_trip)
            if existing_trip is not None:
                already_exists = True
                print("Trip already exists in the database.")
        except ValidationError as e:
            print(f"Validation error: {str(e)}")
            return ResponseBody(
                {"error": str(e)},
                "Error while validating trip data",
                status.HTTP_400_BAD_REQUEST,
            )

        result = client.post_trip([trip.itinerary], [trip.id])
        if len(result) != 0:
            # forwarding the authentication cookie
            voyage_cookie = rq.cookies.get("voyage_at")

            # Forward the cookie in the outgoing POST request
            if not already_exists:
                print("Trip created")
                user_trip_response = request.post(
                    f"http://user-management:8080/trips/save",
                    params={"trip_id": str(trip.id)},
                    cookies={"voyage_at": voyage_cookie} if voyage_cookie else None,
                    timeout=10,
                )

                if user_trip_response.status_code != 200:
                    client.delete_trip(trip.id)
                    return ResponseBody(
                        {},
                        user_trip_response.text,
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            return ResponseBody({"trip_id": trip.id}, "Trips saved")
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
        result = await redis_client.get(str(id))
        print("Redis result:", result)
        if result is not None:
            print("itinerary from Redis:", result)
            # If from Redis, result is already a JSON string
            return ResponseBody({"itinerary": json.loads(result)})

        # Get from MongoDB
        result = client.get_trip_by_id(id)
        if result is not None:
            print("itinerary from DB:", type(result))
            # Ensure Trip object is properly serialized
            if isinstance(result, Trip):
                return ResponseBody({"itinerary": result.model_dump()})
            # If string, parse it
            elif isinstance(result, str):
                return ResponseBody({"itinerary": json.loads(result)})
            # If already a dict, use it directly
            else:
                return ResponseBody({"itinerary": result})

        return ResponseBody({}, "No trip found for this id.", status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error fetching trip from the database: {str(e)}")
        return ResponseBody(
            {"error": str(e)},
            "Error while fetching for the trip by id.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.put("/trip/{id}")
async def update_trip(id: str, trip: Trip):
    client = DBClient()
    try:
        if client.put_trip_by_doc_id(id, trip):
            return ResponseBody(
                {"updated": True}, "Trip Updated with sucess!", status.HTTP_201_CREATED
            )
        return ResponseBody({}, "No trip updated!", status.HTTP_204_NO_CONTENT)
    except Exception as e:

        return ResponseBody(
            {"error": e}, "Unexpected error!", status.HTTP_400_BAD_REQUEST
        )


@router.post("/trip/{trip_id}/regenerate-activity")
async def regenerate_activity(trip_id: str, activity: dict):
    try:
        recommendations_url = (
            f"http://recommendations:8080/trip/{trip_id}/regenerate-activity"
        )
        response = request.post(recommendations_url, json=activity, timeout=40)

        if response.status_code != 200:
            return ResponseBody(
                {"error": response.text},
                "Error from recommendations service",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        updated_itinerary = response.json()["response"]["itinerary"]
        trip = Trip(**updated_itinerary)

        await redis_client.set(str(trip_id), json.dumps(trip.model_dump()), expire=3600)

        return ResponseBody(
            {"itinerary": updated_itinerary},
            "Activity regenerated successfully",
            status.HTTP_200_OK,
        )

    except Exception as e:
        print(f"Error regenerating activity: {str(e)}")
        return ResponseBody(
            {"error": str(e)},
            "Error regenerating activity",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

# delete activity
@router.delete("/trip/{trip_id}/activity/{activity_id}")
async def delete_activity(trip_id: str, activity_id: str):
    try:
        recommendations_url = f"http://recommendations:8080/trip/{trip_id}/delete-activity/{activity_id}"
        response = request.delete(recommendations_url, timeout=40)

        if response.status_code != 200:
            return ResponseBody(
                {"error": response.text},
                "Error from recommendations service",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        updated_itinerary = response.json()["response"]["itinerary"]
        trip = Trip(**updated_itinerary)

        # Update in Redis cache
        await redis_client.set(str(trip_id), json.dumps(trip.model_dump()), expire=3600)

        # Return response in the same structure as regenerate_activity
        return ResponseBody(
            {"response": {"itinerary": updated_itinerary}},
            "Activity deleted successfully",
            status.HTTP_200_OK,
        )

    except Exception as e:
        print(f"Error deleting activity: {str(e)}")
        return ResponseBody(
            {"error": str(e)},
            "Error deleting activity",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
