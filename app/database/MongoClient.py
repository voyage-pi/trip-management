from app.schemas.trips_schema import TripList,Trip
from pymongo import MongoClient 
from dotenv import load_dotenv
import os 

load_dotenv()


mongoHost= os.getenv("MONGO_HOST","mongo-trip")
mongoPort= os.getenv("MONGO_PORT",27017)
mongoUser = os.getenv("MONGO_USER")
mongoPwd = os.getenv("MONGO_PASSWORD")
mongoDatabase = os.getenv("MONGO_DATABASE","voyage-db")

class DBClient():
    def __init__(self):
        url=f"mongodb://{mongoUser}:{mongoPwd}@{mongoHost}:{mongoPort}/"
        self.client=MongoClient(url)
        self.db=self.client[str(mongoDatabase)]
        self.collection=self.db["trips"]

    def insert_trip(self,trip:TripList):
        data=trip["trips"]
        result=self.collection.insert_many(data)
        return result 

