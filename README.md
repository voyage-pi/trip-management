
# **📍 Trip Management Service**
A FastAPI-based microservice for managing user trips and user data.

---

## **🌟 Table of Contents**
- [Overview](#-overview)
- [Technologies Used](#-technologies-used)
- [Setup & Installation](#-setup--installation)
- [API Endpoints](#-api-endpoints)

---

## **📌 Overview**
The **Trip Management Service** provides endpoints for:
1. Creating users and trips.
2. Fetching user information and trips.

### **🔹 Features**
✔ Create **users** with personalized data  
✔ Add and manage **trips** for each user  
✔ Retrieve **user info** and **trips**  

---

## **🛠️ Technologies Used**
| **Technology** | **Usage** |
|---------------|----------|
| Python 3.12   | Backend |
| FastAPI       | API Framework |
| Uvicorn       | ASGI Server |
| Docker        | Containerization |

---

## **🚀 Setup & Installation**
### **1️⃣ Clone the Repository**
```sh
git clone https://github.com/your-org/trip-management.git
cd trip-management
```

### **2️⃣ Create a Virtual Environment (Optional)**
```sh
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scriptsctivate     # On Windows
```

### **3️⃣ Install Dependencies**
```sh
pip install -r requirements.txt
```

### **4️⃣ Run the Service**
#### **Locally**
```sh
uvicorn app.main:app --reload --port 8080
```

#### **Using Docker**
```sh
docker-compose up --build
```

---

## **🛠️ API Endpoints**

### **📍 Create User**
#### **`POST /api/user/{user}`**
Creates a new user with the provided user data.

#### **Request Body**
```json
{
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
```

#### **Example Request**
```sh
curl -X POST "http://localhost:8080/api/user/@ruimachado"   -H "Content-Type: application/json"   -d '{
  "name": "Rui Machado",
  "tag": "@ruimachado",
  "image": "path_to_image.jpg",
  "stats": {
    "trips": 5,
    "friends": 5,
    "saved": 4,
    "countries": 4
  }
  }'
```

#### **Example Response**
```json
{
    "name": "Rui Machado",
    "tag": "@ruimachado",
    "image": "path_to_image.jpg",
    "stats": {
      "trips": 5,
      "friends": 5,
      "saved": 4,
      "countries": 4
    }
}
```

---

### **📍 Create Trip**
#### **`POST /api/trips/{user_id}/{trip}`**
Creates a new trip for the specified user.

#### **Request Body**
```json
{
  "id": 6,
  "image": "https://example.com/image.jpg",
  "days": 7,
  "people": 4,
  "destinations": 5,
  "name": "Trip to Paris",
  "date": "10 Jul 2025 - 17 Jul 2025",
  "status": "upcoming"
}
```

#### **Example Request**
```sh
curl -X POST "http://localhost:8080/api/trips/ruimachado/paristrip"   -H "Content-Type: application/json"   -d '{
    "id": 6,
    "image": "https://example.com/image.jpg",
    "days": 7,
    "people": 4,
    "destinations": 5,
    "name": "Trip to Paris",
    "date": "10 Jul 2025 - 17 Jul 2025",
    "status": "upcoming"
  }'
```

#### **Example Response**
```json
{
  "id": 6,
  "image": "https://example.com/image.jpg",
  "days": 7,
  "people": 4,
  "destinations": 5,
  "name": "Trip to Paris",
  "date": "10 Jul 2025 - 17 Jul 2025",
  "status": "upcoming"
}
```

---

### **📍 Fetch User Info**
#### **`GET /api/user/{user_tag}`**
Fetches user info for the given user tag.

#### **Example Request**
```sh
curl http://localhost:8080/api/user/ruimachado
```

#### **Example Response**
```json
{
  "name": "Rui Machado",
  "tag": "@ruimachado",
  "image": "../src/assets/rui.jpg",
  "stats": {
    "trips": 5,
    "friends": 5,
    "saved": 4,
    "countries": 4
  }
}
```

---

### **📍 Fetch User Trips**
#### **`GET /api/trips/{user_tag}`**
Fetches the trips for the given user tag.

#### **Example Request**
```sh
curl http://localhost:8080/api/trips/ruimachado
```

#### **Example Response**
```json
{
  "trips": [
    {
      "id": 1,
      "image": "https://example.com/image1.jpg",
      "days": 4,
      "people": 2,
      "destinations": 3,
      "name": "Trip to Bali",
      "date": "18 May 2025 - 23 May 2025",
      "status": "drafted"
    }
  ]
}
```

---

## **🔀 Data Flow**
1. User creates a trip using the `POST /api/trips/{user_id}/{trip}` endpoint.
2. User creates a user using the `POST /api/user/{user}` endpoint.
3. User fetches user info and trips via `GET /api/user/{user_tag}` and `GET /api/trips/{user_tag}`.

---