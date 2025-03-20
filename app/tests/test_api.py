from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Sample user and trip data
mock_user_data = {
    "name": "John Doe",
    "tag": "@johndoe",
    "image": "path_to_image.jpg",
    "stats": {
        "trips": 2,
        "friends": 3,
        "saved": 1,
        "countries": 2
    }
}

mock_trip_data = {
    "id": 6,
    "image": "https://example.com/image.jpg",
    "days": 7,
    "people": 4,
    "destinations": 5,
    "name": "Trip to Paris",
    "date": "10 Jul 2025 - 17 Jul 2025",
    "status": "upcoming",
    "user_tag": "@ruimachado",
}

# Test user creation
def test_create_user():
    response = client.post("/api/user/@johndoe", json=mock_user_data)
    assert response.status_code == 200
    assert response.json() == mock_user_data

# Test trip creation
def test_create_trip():
    response = client.post("/api/trips/@ruimachado", json=mock_trip_data)
    assert response.status_code == 200
    assert response.json() == mock_trip_data

# Test fetching user info
def test_get_user_info():
    response = client.get("/api/user/@johndoe")
    assert response.status_code == 200
    assert response.json()["tag"] == "@johndoe"
    assert response.json()["name"] == "John Doe"

# Test fetching trips of a user
def test_get_user_trips():
    response = client.get("/api/trips/@ruimachado") 
    assert response.status_code == 200
    assert len(response.json()["trips"]) > 0
    assert response.json()["trips"][0]["name"] == "Trip to Bali"
    assert response.json()["trips"][0]["status"] == "drafted"
