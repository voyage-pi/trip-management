from fastapi import APIRouter

router = APIRouter(
    prefix="/api",
    tags=["base"],
    responses={404: {"description": "Not found"}},
)


@router.get("/")
async def read_root():
    return {"Hello": "World!"}
