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
from typing import List, Union
from datetime import datetime, timedelta

router = APIRouter(
    prefix="/api",
    tags=["trips"],
    responses={404: {"description": "Trips not found"}},
)

USER_MANAGEMENT_URL = "http://user-management:8080"

# create global redis instance
redis_client = RedisClient()


# Mock trips data
@router.post("/trips")
async def trip_creation(forms: Form,rq:Request):
    try:
        # generate document Id for itinerary document and cache
        documentID = ObjectId()
        trip_type = forms.tripType
        display_name = forms.display_name
        country = forms.country
        city = forms.city
        voyage_cookie = rq.cookies.get("voyage_at")
        questionnaire = []
        for q in forms.preferences.questions:
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
        print(response.json())
        itinerary["trip_type"]=trip_type.value
        itinerary["country"]=country
        itinerary["city"]=city
        
        # Store original location data for regeneration
        itinerary["original_place_data"] = forms.data_type.model_dump()
        
        # Extract and store coordinates based on trip type
        if trip_type.value == "zone":
            itinerary["center_coordinates"] = {
                "latitude": forms.data_type.center.latitude,
                "longitude": forms.data_type.center.longitude
            }
        elif trip_type.value == "place":
            itinerary["place_coordinates"] = {
                "latitude": forms.data_type.coordinates.latitude,
                "longitude": forms.data_type.coordinates.longitude
            }
        elif trip_type.value == "road":
            itinerary["origin_coordinates"] = {
                "latitude": forms.data_type.origin.location.latitude,
                "longitude": forms.data_type.origin.location.longitude
            }
            itinerary["destination_coordinates"] = {
                "latitude": forms.data_type.destination.location.latitude,
                "longitude": forms.data_type.destination.location.longitude
            }
        
        # casting the dictionary to Trip BaseModel object
        current_trip=dict()
        current_trip["itinerary"]=RoadItinerary(**itinerary).model_dump() if trip_type.value=="road" else Trip(**itinerary).model_dump()
        current_trip["tripId"]=str(documentID)
        # casting the dictionary to Trip BaseModel object
        await redis_client.set(
            str(documentID), json.dumps(current_trip["itinerary"]), expire=3600
        )
        # save preferences if user is logged in
        preference_id = None
        if voyage_cookie:
            # Check if an existing preference_id was provided (for reused preferences)
            if hasattr(forms, 'preference_id') and forms.preference_id:
                preference_id = forms.preference_id
                current_trip["preference_id"] = preference_id
                print(f"Using existing preference ID: {preference_id}")
            else:
                # Create new preferences
                preferences={"name":forms.preferences.preferencesName,"answers":[{"answer":{"value":q["value"]},"question_id":q["question_id"]} for q in questionnaire]}
                response = request.post(
                    "http://user-management:8080/preferences", 
                    json=preferences,
                    timeout=10,
                    cookies={"voyage_at": voyage_cookie} if voyage_cookie else None,
                )
                if response.status_code != 200 and response.status_code != 409:
                    print(f"Error from user-management service: {response.text}")
                    return ResponseBody(
                        {"error": response.text},
                        "User-management service error",
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                preference_id = response.json()["response"]["id"]
                current_trip["preference_id"] = preference_id
                print(f"Created new preference ID: {preference_id}")

        # Add the creator as a participant
        voyage_cookie = rq.cookies.get("voyage_at")
        if voyage_cookie:
            user_trip_data = {
                "trip_id": str(documentID),
                "is_group": bool(forms.is_group)
            }
            # Add preference_id if it exists
            if preference_id:
                user_trip_data["preference_id"] = preference_id
                
            user_trip_response = request.post(
                f"{USER_MANAGEMENT_URL}/trips/save",
                json=user_trip_data,
                cookies={"voyage_at": voyage_cookie},
                timeout=10,
            )
            if user_trip_response.status_code != 200:
                print(f"Failed to add creator as participant: {user_trip_response.text}")

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
            existing_trip = client.get_trip_by_id(str(trip.id))
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
                user_trip_data = {
                    "trip_id": str(trip.id),
                    "is_group": bool(trip.is_group)
                }
                # Add preference_id if it exists
                if trip.preference_id is not None:
                    user_trip_data["preference_id"] = trip.preference_id
                    
                user_trip_response = request.post(
                    f"http://user-management:8080/trips/save",
                    json=user_trip_data,
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
async def get_trip(id: str, rq: Request):
    client = DBClient()
    try:
        result = await redis_client.get(str(id))
        if result is not None:
            trip_data = json.loads(result)
            voyage_cookie = rq.cookies.get("voyage_at")
            
            # Get participants data based on authentication status
            participants = []
            if voyage_cookie:
                # Authenticated user - get full participant details
                try:
                    participants_response = request.get(
                        f"{USER_MANAGEMENT_URL}/trips/participants/{id}",
                        cookies={"voyage_at": voyage_cookie},
                        timeout=10
                    )
                    print(participants_response)
                    if participants_response.status_code == 200:
                        participants = participants_response.json()
                        print(participants)
                    else:
                        print(f"Failed to get participants: {participants_response.status_code}")
                        participants = []
                except Exception as e:
                    print(f"Error fetching participants: {str(e)}")
                    participants = []
            else:
                # Guest user - check if trip has participants without getting details
                try:
                    count_response = request.get(
                        f"{USER_MANAGEMENT_URL}/trips/participants-count/{id}",
                        timeout=10
                    )
                    if count_response.status_code == 200:
                        count_data = count_response.json()
                        if count_data.get("has_participants", False):
                            # Return a placeholder to indicate there are participants but we can't see them
                            participants = [{"user_id": "hidden"}]  # Placeholder to indicate participants exist
                        else:
                            participants = []  # No participants - guest can edit
                    else:
                        print(f"Failed to get participant count: {count_response.status_code}")
                        participants = []
                except Exception as e:
                    print(f"Error fetching participant count: {str(e)}")
                    participants = []
            
            return ResponseBody({"itinerary": trip_data, "participants": participants})

        result = client.get_trip_by_id(id)
        if result is not None:
<<<<<<< HEAD
            trip_data = result.model_dump() if isinstance(result, (Trip, RoadItinerary)) else json.loads(result) if isinstance(result, str) else result.model_dump()
=======
            trip_data =  json.loads(result) if isinstance(result, str) else result.model_dump()
>>>>>>> 8e8a546b63723839f394fa2f8b47c9a9293cc2e6
            voyage_cookie = rq.cookies.get("voyage_at")
            
            # Get participants data based on authentication status
            participants = []
            if voyage_cookie:
                # Authenticated user - get full participant details
                try:
                    participants_response = request.get(
                        f"{USER_MANAGEMENT_URL}/trips/participants/{id}",
                        cookies={"voyage_at": voyage_cookie},
                        timeout=10
                    )
                    if participants_response.status_code == 200:
                        participants = participants_response.json()
                    else:
                        print(f"Failed to get participants: {participants_response.status_code}")
                        participants = []
                except Exception as e:
                    print(f"Error fetching participants: {str(e)}")
                    participants = []
            else:
                # Guest user - check if trip has participants without getting details
                try:
                    count_response = request.get(
                        f"{USER_MANAGEMENT_URL}/trips/participants-count/{id}",
                        timeout=10
                    )
                    if count_response.status_code == 200:
                        count_data = count_response.json()
                        if count_data.get("has_participants", False):
                            # Return a placeholder to indicate there are participants but we can't see them
                            participants = [{"user_id": "hidden"}]  # Placeholder to indicate participants exist
                        else:
                            participants = []  # No participants - guest can edit
                    else:
                        print(f"Failed to get participant count: {count_response.status_code}")
                        participants = []
                except Exception as e:
                    print(f"Error fetching participant count: {str(e)}")
                    participants = []
                
            return ResponseBody({"itinerary": trip_data, "participants": participants})

        return ResponseBody({}, "No trip found for this id.", status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error fetching trip from the database: {str(e)}")
        return ResponseBody(
            {"error": str(e)},
            "Error while fetching for the trip by id.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.put("/trip/{id}")
async def update_trip(id: str, trip: Union[Trip, RoadItinerary]):
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
            
        # Create the appropriate trip object based on trip_type
        if trip_type == "road":
            trip = RoadItinerary(**updated_itinerary)
        else:
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
        
        # Create the appropriate trip object based on trip_type
        if trip_type == "road":
            trip = RoadItinerary(**updated_itinerary)
        else:
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

@router.put("/trip/{trip_id}/preferences")
async def update_trip_preferences(trip_id: str, preferences_data: dict, rq: Request):
    """Update trip preferences and regenerate the trip with new preferences"""
    client = DBClient()
    try:
        voyage_cookie = rq.cookies.get("voyage_at")
        if not voyage_cookie:
            return ResponseBody(
                {"error": "Authentication required"},
                "Authentication required",
                status.HTTP_401_UNAUTHORIZED,
            )

        # First try to get trip from Redis
        current_trip = await redis_client.get(str(trip_id))
        
        # If not in Redis, try to get from database
        if not current_trip:
            print(f"Trip {trip_id} not found in Redis, checking database...")
            db_trip = client.get_trip_by_id(trip_id)
            if db_trip is not None:
                print(f"Trip {trip_id} found in database")
                if isinstance(db_trip, (Trip, RoadItinerary)):
                    current_trip = json.dumps(db_trip.model_dump())
                elif isinstance(db_trip, str):
                    current_trip = db_trip
                else:
                    current_trip = json.dumps(db_trip.model_dump())
                
                # Cache the trip in Redis for future requests
                await redis_client.set(str(trip_id), current_trip, expire=3600)
            else:
                print(f"Trip {trip_id} not found in database either")
                return ResponseBody(
                    {"error": "Trip not found"},
                    "Trip not found",
                    status.HTTP_404_NOT_FOUND,
                )
        else:
            print(f"Trip {trip_id} found in Redis")
        
        current_trip_data = json.loads(current_trip)
        
        print(f"Current trip data keys: {list(current_trip_data.keys())}")
        print(f"Current trip data sample: {json.dumps(current_trip_data, indent=2)[:500]}...")
        
        # Get the preference_id from the request
        preference_id = preferences_data.get("preference_id")
        answers = preferences_data.get("answers", [])
        
        if not preference_id:
            return ResponseBody(
                {"error": "Preference ID is required"},
                "Preference ID is required",
                status.HTTP_400_BAD_REQUEST,
            )

        # NOTE: Preferences are already updated by user-management service
        # No need to update them again here to avoid circular dependency

        # Prepare questionnaire for recommendations service
        questionnaire = [{"question_id": answer["question_id"], "value": answer["value"], "type": "scale"} for answer in answers]
        
        # Get trip metadata from current trip or cache
        trip_type = current_trip_data.get('trip_type', 'place')
        country = current_trip_data.get('country')
        city = current_trip_data.get('city')
        is_group = current_trip_data.get('is_group', False)
        
        # For regeneration, we need to get the original trip parameters
        # This might be stored in a separate cache or we need to reconstruct from current data
        
        # Prepare request body for recommendations service (similar to trip creation)
        requestBody = {
            "trip_id": trip_id,
            "questionnaire": questionnaire,
            # We need to get these from the original trip or current trip data
            "start_date": current_trip_data.get('start_date', datetime.now().isoformat()),
            "end_date": current_trip_data.get('end_date', (datetime.now() + timedelta(days=3)).isoformat()),
            "budget": current_trip_data.get('budget', 1000),
            "name": current_trip_data.get('name', 'Updated Trip'),
            "must_visit_places": current_trip_data.get('must_visit_places', []),
            "keywords": current_trip_data.get('keywords', []),
            "country": country,
            "city": city,
            "is_group": is_group,
        }
        
        # Reconstruct the data field based on trip type and available data
        data_field = current_trip_data.get('data')
        if not data_field or (isinstance(data_field, dict) and data_field.get('template_type')):
            # If we don't have the original data structure, create a default one based on trip type
            print(f"Reconstructing data field for trip_type: {trip_type}")
            
            if trip_type == "zone":
                # For zone trips, we need center coordinates and radius
                # Try to extract from the trip data or use defaults
                center_lat = current_trip_data.get('center_latitude', 40.7128)  # Default to NYC
                center_lng = current_trip_data.get('center_longitude', -74.0060)
                radius = current_trip_data.get('radius', 50)  # Default 50km radius
                
                data_field = {
                    "type": "zone",
                    "center": {
                        "latitude": center_lat,
                        "longitude": center_lng
                    },
                    "radius": radius
                }
            elif trip_type == "place":
                # For place trips, we need coordinates and place name
                place_lat = current_trip_data.get('place_latitude', 40.7128)
                place_lng = current_trip_data.get('place_longitude', -74.0060)
                place_name = current_trip_data.get('place_name', city or country or 'Unknown Place')
                
                data_field = {
                    "type": "place",
                    "coordinates": {
                        "latitude": place_lat,
                        "longitude": place_lng
                    },
                    "place_name": place_name,
                    "place_id": current_trip_data.get('place_id')
                }
            elif trip_type == "road":
                # For road trips, we need origin, destination, and polylines
                # This is more complex, might need to extract from activities
                origin_name = current_trip_data.get('origin_name', 'Start Point')
                dest_name = current_trip_data.get('destination_name', 'End Point')
                
                data_field = {
                    "type": "road",
                    "origin": {
                        "coordinates": {
                            "latitude": current_trip_data.get('origin_latitude', 40.7128),
                            "longitude": current_trip_data.get('origin_longitude', -74.0060)
                        },
                        "place_name": origin_name,
                        "place_id": current_trip_data.get('origin_place_id')
                    },
                    "destination": {
                        "coordinates": {
                            "latitude": current_trip_data.get('destination_latitude', 40.7589),
                            "longitude": current_trip_data.get('destination_longitude', -73.9851)
                        },
                        "place_name": dest_name,
                        "place_id": current_trip_data.get('destination_place_id')
                    },
                    "polylines": current_trip_data.get('polylines', '')
                }
        
        print(f"Using data field: {json.dumps(data_field, indent=2)}")
        
        # Add data type and trip type
        requestBody["data"] = data_field
        requestBody["tripType"] = trip_type
        
        print(f"Calling recommendations service with data: {json.dumps(requestBody)[:200]}...")
        
        # Call recommendations service to regenerate trip
        response = request.post(
            "http://recommendations:8080/trip", 
            json=requestBody, 
            timeout=60
        )
        
        if response.status_code != 200:
            return ResponseBody(
                {"error": f"Error from recommendations service: {response.text}"},
                "Error regenerating trip",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        # Process the new itinerary
        itinerary = response.json()["itinerary"]
        itinerary["trip_type"] = trip_type
        itinerary["country"] = country
        itinerary["city"] = city
        
        # Update the trip in cache
        updated_trip = RoadItinerary(**itinerary).model_dump() if trip_type == "road" else Trip(**itinerary).model_dump()
        await redis_client.set(trip_id, json.dumps(updated_trip), expire=3600)
        
        # Also update the trip in the database
        try:
            if trip_type == "road":
                db_updated = client.put_trip_by_doc_id(trip_id, RoadItinerary(**itinerary))
            else:
                db_updated = client.put_trip_by_doc_id(trip_id, Trip(**itinerary))
            print(f"Database update result: {db_updated}")
        except Exception as db_error:
            print(f"Error updating trip in database: {str(db_error)}")
            # Continue even if database update fails, since Redis has the updated trip
        
        # Return the updated trip
        return ResponseBody({
            "response": {
                "itinerary": updated_trip,
                "tripId": trip_id,
                "preference_id": preference_id
            }
        })

    except Exception as e:
        print(f"Error updating trip preferences: {str(e)}")
        import traceback
        traceback.print_exc()
        return ResponseBody(
            {"error": str(e)},
            "Error updating trip preferences",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@router.get("/trip-test-auth")
async def test_auth(rq: Request):
    """Test endpoint to debug authentication issues"""
    try:
        voyage_cookie = rq.cookies.get("voyage_at")
        headers_dict = dict(rq.headers)
        
        return ResponseBody({
            "has_cookie": voyage_cookie is not None,
            "cookie_prefix": voyage_cookie[:10] if voyage_cookie else None,
            "headers": headers_dict,
            "message": "This is a test endpoint"
        })
    except Exception as e:
        print(f"Error in test auth endpoint: {str(e)}")
        return ResponseBody(
            {"error": str(e)},
            "Error in test endpoint",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
