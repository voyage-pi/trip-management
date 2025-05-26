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
        if not guest:
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
            preferences_inserted_id=response.json()["response"]["id"]
            current_trip["preferences_id"]=preferences_inserted_id
            
        if voyage_cookie:
            try:
                user_trip_response = request.post(
                    f"{USER_MANAGEMENT_URL}/trips/save",
                    json={
                        "trip_id": trip_id,
                        "is_group": bool(forms.is_group)
                    },
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
