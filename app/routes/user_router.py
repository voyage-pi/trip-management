from fastapi import APIRouter
from schemas.user_schema import User

router = APIRouter(
    prefix="/api",
    tags=["user"],
    responses={404: {"description": "User not found"}},
)

# Mock user data, you can modify as needed
mock_user = {
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

@router.get("/user", response_model=User)
async def get_user_info():
    return mock_user
