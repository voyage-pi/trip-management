from app.database.CacheClient import RedisClient
from app.schemas.response import ResponseBody
from fastapi import APIRouter, status,Request
from app.schemas.trips_schema import RoadItinerary, Trip, TripSaveRequest,TripResponse
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
        country = forms.country
        city = forms.city
        questionnaire = []
        for user_id, user_questions in forms.questions.items():
            for q in user_questions:
                questionnaire.append(
                    {"question_id": q.question_id, "value": q.value, "type": "scale"}
                )
        # Ensure duration is at least 1 day
        duration = max(1, forms.duration)
        delta = timedelta(days=duration)
        # Convert startDate string to datetime object with proper error handling
        try:
            # Handle ISO format string with Z (UTC) timezone
            if forms.startDate.endswith('Z'):
                start_date = datetime.fromisoformat(forms.startDate.replace('Z', '+00:00'))
            else:
                start_date = datetime.fromisoformat(forms.startDate)
        except (ValueError, TypeError):
            # Default to current date if parsing fails
            print(f"Invalid date format: {forms.startDate}, using current date instead")
            start_date = datetime.now()
            return ResponseBody(
                {},
                "Error connecting to recommendations service",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        end_date = start_date + delta

        requestBody = {
            "trip_id": str(documentID),
            "questionnaire": questionnaire,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "budget": forms.budget,
            # adding the display name as attribute to the trip
            "name": display_name,
            "must_visit_places": [mvp.model_dump() for mvp in forms.must_visit_places],
            "keywords": forms.keywords,
            "country": country,
            "city": city,
            "is_group": forms.is_group,
        }

        requestBody["data"] = forms.data_type.model_dump()
        requestBody["tripType"] = trip_type.value
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
        itinerary["trip_type"]=trip_type.value
        itinerary["country"]=country
        itinerary["city"]=city
        # casting the dictionary to Trip BaseModel object
        current_trip=dict()
        current_trip["itinerary"]=RoadItinerary(**itinerary).model_dump() if trip_type.value=="road" else Trip(**itinerary).model_dump()
        current_trip["tripId"]=str(documentID)
        # casting the dictionary to Trip BaseModel object
        await redis_client.set(
            str(documentID), json.dumps(current_trip["itinerary"]), expire=3600
        )
        return ResponseBody(TripResponse(**current_trip).model_dump())
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
        # add the trip_type onto the itinerary itself
        trip.itinerary.trip_type=trip.trip_type
        trip.itinerary.country=trip.itinerary.country
        trip.itinerary.city=trip.itinerary.city
        trip.itinerary.is_group=trip.is_group
        result = client.post_trip([trip.itinerary], [trip.id])
        if len(result) != 0:
            # forwarding the authentication cookie
            voyage_cookie = rq.cookies.get("voyage_at")

            # Forward the cookie in the outgoing POST request
            if not already_exists:
                print("Trip created")
                user_trip_response = request.post(
                    f"http://user-management:8080/trips/save",
                    json={
                        "trip_id": str(trip.id),
                        "is_group": bool(trip.is_group)
                            },
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
        if result is not None:
            # If from Redis, result is already a JSON string
            return ResponseBody({"itinerary": json.loads(result)})

        # Get from MongoDB
        result = client.get_trip_by_id(id)
        if result is not None:
            # Ensure Trip object is properly serialized
            if isinstance(result, Trip):
                return ResponseBody({"itinerary": result.model_dump()})
            # If string, parse it
            elif isinstance(result, str):
                return ResponseBody({"itinerary": json.loads(result)})
            # If already a dict, use it directly
            else:
                return ResponseBody({"itinerary": result.model_dump()})

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
        # First get the current trip to preserve trip_type
        current_trip = await redis_client.get(str(trip_id))
        if current_trip:
            current_trip_data = json.loads(current_trip)
            trip_type = current_trip_data.get('trip_type')
            
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
        
        # Preserve the trip_type in the updated itinerary
        if current_trip and trip_type:
            updated_itinerary['trip_type'] = trip_type
            updated_itinerary['tripId'] = trip_id

            
        # Ensure other required fields are present
        if 'country' in current_trip_data:
            updated_itinerary['country'] = current_trip_data.get('country')
        if 'city' in current_trip_data:
            updated_itinerary['city'] = current_trip_data.get('city')
        if 'is_group' in current_trip_data:
            updated_itinerary['is_group'] = current_trip_data.get('is_group')
            
        trip = Trip(**updated_itinerary)


        await redis_client.set(str(trip_id), json.dumps(trip.model_dump()), expire=3600)

        print("trip", trip)

        return TripResponse(itinerary=trip, tripId=trip_id).model_dump()

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
        # First get the current trip to preserve trip_type
        current_trip = await redis_client.get(str(trip_id))
        if not current_trip:
            return ResponseBody(
                {"error": "Trip not found"},
                "Trip not found",
                status.HTTP_404_NOT_FOUND,
            )
        current_trip_data = json.loads(current_trip)
        trip_type = current_trip_data.get('trip_type')

        recommendations_url = f"http://recommendations:8080/trip/{trip_id}/delete-activity/{activity_id}"
        response = request.delete(recommendations_url, timeout=40)

        if response.status_code != 200:
            return ResponseBody(
                {"error": response.text},
                "Error from recommendations service",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        updated_itinerary = response.json()["response"]["itinerary"]
        # Preserve the trip_type in the updated itinerary
        if trip_type:
            updated_itinerary['trip_type'] = trip_type
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
