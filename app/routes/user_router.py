from fastapi import APIRouter, HTTPException
from app.schemas.user_schema import User
import json

with open("app/models/users.json", "r") as f:
    users = json.load(f)

router = APIRouter(
    prefix="/api",
    tags=["user"],
    responses={404: {"description": "User not found"}},
)

def validate_user_tag(user_tag: str):
    if user_tag not in [user["tag"] for user in users["users"]]:
        raise HTTPException(status_code=404, detail="User tag not found")

@router.get("/user/{user_tag}", response_model=User)
async def get_user_info(user_tag: str):
    validate_user_tag(user_tag)
    user = next((user for user in users["users"] if user["tag"] == user_tag), None)
    
    if user is None:
        raise HTTPException(status_code=404, detail="User tag not found")
    
    return user


@router.post("/user/{user_tag}", response_model=User)
async def create_user(user_tag: str, user: User):
    if any(u["tag"] == user_tag for u in users["users"]):
        raise HTTPException(status_code=400, detail="User tag already exists")
    
    new_user = user.model_dump()
    new_user["tag"] = user_tag
    users["users"].append(new_user)

    with open('users.json', 'w') as f:
        json.dump(users, f, indent=2)
    return new_user

    return new_user