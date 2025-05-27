from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from fastapi.websockets import WebSocketState
from app.database.CacheClient import RedisClient
from app.schemas.response import ResponseBody
from app.schemas.trips_schema import RoadItinerary, Trip, TripSaveRequest, TripResponse
from app.schemas.forms_schema import Form
from app.database.MongoClient import DBClient
import requests as request
import json
import asyncio
from pydantic import ValidationError
from bson import ObjectId
from datetime import datetime, timedelta
import traceback

router = APIRouter(
    prefix="/ws",
    tags=["websockets"],
)

USER_MANAGEMENT_URL = "http://user-management:8080"
redis_client = RedisClient()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, trip_id: str):
        await websocket.accept()
        self.active_connections[trip_id] = websocket
    
    def disconnect(self, trip_id: str):
        if trip_id in self.active_connections:
            del self.active_connections[trip_id]
    
    async def send_message(self, trip_id: str, message: dict):
        if trip_id in self.active_connections:
            websocket = self.active_connections[trip_id]
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(f"Error sending message: {e}")
                    self.disconnect(trip_id)

manager = ConnectionManager()

@router.websocket("/trip-creation")
async def websocket_trip_creation(websocket: WebSocket):
    trip_id = None
    try:
        await websocket.accept()
        
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to trip creation service",
            "progress": 0
        })
        
        form_data = await websocket.receive_json()
        guest= True if "guest" in form_data else False
        try:
            forms = Form(**form_data)
        except ValidationError as e:
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid form data: {str(e)}",
                "progress": 0
            })
            return
        
        trip_id = str(ObjectId())
        manager.active_connections[trip_id] = websocket
        
        await websocket.send_json({
            "type": "progress",
            "message": "Processing trip request...",
            "progress": 10,
            "trip_id": trip_id
        })
        
        trip_type = forms.tripType
        display_name = forms.display_name
        country = forms.country
        city = forms.city
        questionnaire = []
        for q in forms.preferences.questions:
            questionnaire.append(
                {"question_id": q.question_id, "value": q.value, "type": "scale"}
            )
        
        duration = max(1, forms.duration)
        delta = timedelta(days=duration)
        
        try:
            if forms.startDate.endswith('Z'):
                start_date = datetime.fromisoformat(forms.startDate.replace('Z', '+00:00'))
            else:
                start_date = datetime.fromisoformat(forms.startDate)
        except (ValueError, TypeError):
            print(f"Invalid date format: {forms.startDate}, using current date instead")
            start_date = datetime.now()
            await websocket.send_json({
                "type": "error",
                "message": "Invalid date format",
                "progress": 10
            })
            return
        
        end_date = start_date + delta
        
        await websocket.send_json({
            "type": "progress",
            "message": "Preparing request for recommendations service...",
            "progress": 20
        })
        
        requestBody = {
            "trip_id": trip_id,
            "questionnaire": questionnaire,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "budget": forms.budget,
            "name": display_name,
            "must_visit_places": [mvp.model_dump() for mvp in forms.must_visit_places],
            "keywords": forms.keywords,
            "country": country,
            "city": city,
            "is_group": forms.is_group,
        }
        
        requestBody["data"] = forms.data_type.model_dump()
        requestBody["tripType"] = trip_type.value
        
        await websocket.send_json({
            "type": "progress",
            "message": "Calling recommendations service...",
            "progress": 30
        })
        
        response = request.post(
            "http://recommendations:8080/trip", json=requestBody, timeout=60
        )
        
        if response.status_code != 200:
            await websocket.send_json({
                "type": "error",
                "message": f"Error from recommendations service: {response.text}",
                "progress": 30
            })
            return
        
        await websocket.send_json({
            "type": "progress",
            "message": "Processing recommendations response...",
            "progress": 70
        })
        
        itinerary = response.json()["itinerary"]
        itinerary["trip_type"] = trip_type.value
        itinerary["country"] = country
        itinerary["city"] = city
        
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
                "latitude": forms.data_type.origin.coordinates.latitude,
                "longitude": forms.data_type.origin.coordinates.longitude
            }
            itinerary["destination_coordinates"] = {
                "latitude": forms.data_type.destination.coordinates.latitude,
                "longitude": forms.data_type.destination.coordinates.longitude
            }
        
        current_trip = dict()
        current_trip["itinerary"] = RoadItinerary(**itinerary).model_dump() if trip_type.value == "road" else Trip(**itinerary).model_dump()
        current_trip["tripId"] = trip_id
        
        await websocket.send_json({
            "type": "progress",
            "message": "Saving to cache...",
            "progress": 80
        })
        
        await redis_client.set(
            trip_id, json.dumps(current_trip["itinerary"]), expire=3600
        )
        
        await websocket.send_json({
            "type": "progress",
            "message": "Adding creator as participant...",
            "progress": 90
        })
        
        voyage_cookie = None
        cookie_header = None
        for header_name, header_value in websocket.headers.items():
            if header_name.lower() == 'cookie':
                cookie_header = header_value
                break
        if cookie_header:
            cookies = {}
            for cookie in cookie_header.split(';'):
                if '=' in cookie:
                    key, value = cookie.strip().split('=', 1)
                    cookies[key] = value
            voyage_cookie = cookies.get('voyage_at')
        
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
                    await websocket.send_json({
                        "type": "error",
                        "message": "Couldn't save the preferences of the user for this trip.",
                    })
                preference_id = response.json()["response"]["id"]
                current_trip["preference_id"] = preference_id
                print(f"Created new preference ID: {preference_id}")
            
        if voyage_cookie and not guest:
            try:
                user_trip_data = {
                    "trip_id": trip_id,
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
                    await websocket.send_json({
                        "type": "error",
                        "message": user_trip_response.text,
                    })
            except Exception as e:
                print(f"Error adding creator as participant: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })
        
        await websocket.send_json({
            "type": "success",
            "message": "Trip created successfully!",
            "progress": 100,
            "trip_id": trip_id,
            "data": TripResponse(**current_trip).model_dump()
        })
        
    except WebSocketDisconnect:
        if trip_id:
            manager.disconnect(trip_id)
        print("WebSocket disconnected")
    except Exception as e:
        print(f"Error in WebSocket trip creation: {str(e)}")
        print(traceback.format_exc())
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error creating trip: {str(e)}",
                "progress": 0
            })
        except:
            pass
        if trip_id:
            manager.disconnect(trip_id) 

@router.websocket("/trip-regeneration/{trip_id}")
async def websocket_trip_regeneration(websocket: WebSocket, trip_id: str):
    """Handle trip regeneration via WebSocket for preference updates"""
    try:
        await websocket.accept()
        
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to trip regeneration service",
            "progress": 0,
            "trip_id": trip_id
        })
        
        # Wait for preferences data
        preferences_data = await websocket.receive_json()
        
        await websocket.send_json({
            "type": "progress",
            "message": "Validating preferences data...",
            "progress": 10
        })
        
        # Extract data from the message
        preference_id = preferences_data.get("preference_id")
        answers = preferences_data.get("answers", [])
        
        if not preference_id:
            await websocket.send_json({
                "type": "error",
                "message": "Preference ID is required",
                "progress": 10
            })
            return
        
        await websocket.send_json({
            "type": "progress", 
            "message": "Loading trip data...",
            "progress": 20
        })
        
        # Get trip data (from Redis or database)
        client = DBClient()
        current_trip = await redis_client.get(str(trip_id))
        
        if not current_trip:
            db_trip = client.get_trip_by_id(trip_id)
            if db_trip is not None:
                if isinstance(db_trip, Trip):
                    current_trip = json.dumps(db_trip.model_dump())
                elif isinstance(db_trip, str):
                    current_trip = db_trip
                else:
                    current_trip = json.dumps(db_trip.model_dump())
                await redis_client.set(str(trip_id), current_trip, expire=3600)
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Trip not found",
                    "progress": 20
                })
                return
        
        current_trip_data = json.loads(current_trip)
        
        print(f"DEBUG: Current trip data keys: {list(current_trip_data.keys())}")
        print(f"DEBUG: Current trip data: {json.dumps(current_trip_data, indent=2)[:1000]}...")
        
        await websocket.send_json({
            "type": "progress",
            "message": "Preparing regeneration request...",
            "progress": 30
        })
        
        # Prepare questionnaire for recommendations service
        questionnaire = [{"question_id": answer["question_id"], "value": answer["value"], "type": "scale"} for answer in answers]
        
        # Get trip metadata
        trip_type = current_trip_data.get('trip_type', 'place')
        country = current_trip_data.get('country')
        city = current_trip_data.get('city')
        is_group = current_trip_data.get('is_group', False)
        
        # Function to extract location from trip activities (fallback for older trips)
        def extract_location_from_activities(trip_data):
            """Extract location coordinates from existing trip activities"""
            try:
                days = trip_data.get('days', [])
                if not days:
                    return None
                
                # Look through all activities to find location data
                for day in days:
                    for activity_type in ['morning_activities', 'afternoon_activities', 'evening_activities']:
                        activities = day.get(activity_type, [])
                        for activity in activities:
                            place = activity.get('place', {})
                            location = place.get('location', {})
                            if location.get('latitude') and location.get('longitude'):
                                return {
                                    'latitude': location['latitude'],
                                    'longitude': location['longitude'],
                                    'place_name': place.get('name', city or country or 'Unknown Place'),
                                    'place_id': place.get('id')
                                }
                return None
            except Exception as e:
                print(f"Error extracting location from activities: {e}")
                return None
        
        # Use stored location data for regeneration
        data_field = current_trip_data.get('original_place_data')
        
        if data_field:
            print(f"DEBUG: Using stored original place data: {json.dumps(data_field, indent=2)}")
        else:
            print(f"DEBUG: No stored place data found, reconstructing from stored coordinates")
            
            # Fallback: reconstruct from stored coordinate fields
            if trip_type == "zone":
                center_coords = current_trip_data.get('center_coordinates')
                if center_coords:
                    data_field = {
                        "type": "zone",
                        "center": {
                            "latitude": center_coords['latitude'],
                            "longitude": center_coords['longitude']
                        },
                        "radius": current_trip_data.get('radius', 50)
                    }
                else:
                    # Last resort: extract from activities
                    location_info = extract_location_from_activities(current_trip_data)
                    if location_info:
                        data_field = {
                            "type": "zone",
                            "center": {
                                "latitude": location_info['latitude'],
                                "longitude": location_info['longitude']
                            },
                            "radius": 50
                        }
                    else:
                        # Final fallback to NYC
                        data_field = {
                            "type": "zone",
                            "center": {"latitude": 40.7128, "longitude": -74.0060},
                            "radius": 50
                        }
                        
            elif trip_type == "place":
                place_coords = current_trip_data.get('place_coordinates')
                if place_coords:
                    data_field = {
                        "type": "place",
                        "coordinates": {
                            "latitude": place_coords['latitude'],
                            "longitude": place_coords['longitude']
                        },
                        "place_name": city or country or 'Unknown Place',
                        "place_id": None
                    }
                else:
                    # Last resort: extract from activities
                    location_info = extract_location_from_activities(current_trip_data)
                    if location_info:
                        data_field = {
                            "type": "place",
                            "coordinates": {
                                "latitude": location_info['latitude'],
                                "longitude": location_info['longitude']
                            },
                            "place_name": location_info['place_name'],
                            "place_id": location_info.get('place_id')
                        }
                    else:
                        # Final fallback
                        data_field = {
                            "type": "place",
                            "coordinates": {"latitude": 40.7128, "longitude": -74.0060},
                            "place_name": city or country or 'Unknown Place',
                            "place_id": None
                        }
                        
            elif trip_type == "road":
                origin_coords = current_trip_data.get('origin_coordinates')
                dest_coords = current_trip_data.get('destination_coordinates')
                
                if origin_coords and dest_coords:
                    data_field = {
                        "type": "road",
                        "origin": {
                            "coordinates": {
                                "latitude": origin_coords['latitude'],
                                "longitude": origin_coords['longitude']
                            },
                            "place_name": "Origin",
                            "place_id": None
                        },
                        "destination": {
                            "coordinates": {
                                "latitude": dest_coords['latitude'],
                                "longitude": dest_coords['longitude']
                            },
                            "place_name": "Destination",
                            "place_id": None
                        },
                        "polylines": current_trip_data.get('polylines', '')
                    }
                else:
                    # Last resort: extract from activities
                    location_info = extract_location_from_activities(current_trip_data)
                    if location_info:
                        data_field = {
                            "type": "road",
                            "origin": {
                                "coordinates": {
                                    "latitude": location_info['latitude'],
                                    "longitude": location_info['longitude']
                                },
                                "place_name": location_info['place_name'],
                                "place_id": location_info.get('place_id')
                            },
                            "destination": {
                                "coordinates": {
                                    "latitude": location_info['latitude'] + 0.1,
                                    "longitude": location_info['longitude'] + 0.1
                                },
                                "place_name": "End Point",
                                "place_id": None
                            },
                            "polylines": ''
                        }
                    else:
                        # Final fallback
                        data_field = {
                            "type": "road",
                            "origin": {
                                "coordinates": {"latitude": 40.7128, "longitude": -74.0060},
                                "place_name": "Start Point",
                                "place_id": None
                            },
                            "destination": {
                                "coordinates": {"latitude": 40.7589, "longitude": -73.9851},
                                "place_name": "End Point", 
                                "place_id": None
                            },
                            "polylines": ''
                        }
        
        print(f"DEBUG: Using data field: {json.dumps(data_field, indent=2)}")
        
        # Prepare request body for recommendations service
        requestBody = {
            "trip_id": trip_id,
            "questionnaire": questionnaire,
            "start_date": current_trip_data.get('start_date', datetime.now().isoformat()),
            "end_date": current_trip_data.get('end_date', (datetime.now() + timedelta(days=3)).isoformat()),
            "budget": current_trip_data.get('budget', 1000),
            "name": current_trip_data.get('name', 'Updated Trip'),
            "must_visit_places": current_trip_data.get('must_visit_places', []),
            "keywords": current_trip_data.get('keywords', []),
            "country": country,
            "city": city,
            "is_group": is_group,
            "data": data_field,
            "tripType": trip_type
        }
        
        await websocket.send_json({
            "type": "progress",
            "message": "Calling recommendations service...",
            "progress": 40
        })
        
        # Call recommendations service
        response = request.post(
            "http://recommendations:8080/trip", 
            json=requestBody, 
            timeout=120
        )
        
        if response.status_code != 200:
            await websocket.send_json({
                "type": "error",
                "message": f"Error from recommendations service: {response.text}",
                "progress": 40
            })
            return
        
        await websocket.send_json({
            "type": "progress",
            "message": "Processing new itinerary...",
            "progress": 80
        })
        
        # Process the new itinerary
        itinerary = response.json()["itinerary"]
        itinerary["trip_type"] = trip_type
        itinerary["country"] = country
        itinerary["city"] = city
        
        # Update the trip in cache
        updated_trip = RoadItinerary(**itinerary).model_dump() if trip_type == "road" else Trip(**itinerary).model_dump()
        await redis_client.set(trip_id, json.dumps(updated_trip), expire=3600)
        
        await websocket.send_json({
            "type": "progress",
            "message": "Updating database...",
            "progress": 90
        })
        
        # Update in database
        try:
            if trip_type == "road":
                client.put_trip_by_doc_id(trip_id, RoadItinerary(**itinerary))
            else:
                client.put_trip_by_doc_id(trip_id, Trip(**itinerary))
        except Exception as db_error:
            print(f"Database update error: {db_error}")
            # Continue even if database update fails
        
        # Send success response
        await websocket.send_json({
            "type": "success",
            "message": "Trip regenerated successfully!",
            "progress": 100,
            "data": {
                "itinerary": updated_trip,
                "tripId": trip_id,
                "preference_id": preference_id
            }
        })
        
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for trip {trip_id}")
    except Exception as e:
        print(f"Error in trip regeneration: {str(e)}")
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error regenerating trip: {str(e)}",
                "progress": -1
            })
        except:
            pass 
