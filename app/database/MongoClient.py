from app.schemas.trips_schema import Trip
from pymongo import MongoClient 
from typing import List
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

    # Returns the list of id's of the inserted documents 
    def post_trip(self,trip:List[Trip])->List[str]:
        r=self.collection.insert_many(trip)
        ids= [str(_id) for _id in r.inserted_ids]
        return ids


    def get_trip_by_user_id(self,id:str):
        result=list(self.collection.find({"people":id}))
        parsed_documents = [{**doc, '_id': str(doc['_id'])} for doc in result]
        return parsed_documents

