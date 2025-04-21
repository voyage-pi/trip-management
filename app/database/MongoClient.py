from app.schemas.trips_schema import Trip
from pymongo import MongoClient
from bson import ObjectId
from typing import List,Union
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
from bson import ObjectId
import os

load_dotenv()


mongoHost = os.getenv("MONGO_HOST", "mongo-trip")
mongoPort = os.getenv("MONGO_PORT", 27017)
mongoUser = os.getenv("MONGO_USER")
mongoPwd = os.getenv("MONGOPASSWORD")
mongoDatabase = os.getenv("MONGO_DATABASE", "voyage-db")



class DBClient:
    def __init__(self):
        try:
            url = f"mongodb://{mongoUser}:{mongoPwd}@{mongoHost}:{mongoPort}/"
            self.client = MongoClient(url)
            self.db = self.client[str(mongoDatabase)]
            self.collection = self.db["trips"]
        except PyMongoError as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")

    def post_trip(self, trips: List[Trip], ids: List[str] = []) -> Union[List[str], str]:
        assert (len(trips) == len(ids) or not ids), "Length of trips and ids must match or ids must be empty"
        assert (len(trips) != 0), "Trips list must not be empty"
        documents = []

        for i, t in enumerate(trips):
            try:
                if ids:
                    doc = {"_id": ObjectId(ids[i]), **t.model_dump()}
                else:
                    doc = t.model_dump()
                documents.append(doc)
            except Exception as e:
                return f"Error preparing document for insertion: {e}"

        try:
            r = self.collection.insert_many(documents)
            inserted_ids = [str(_id) for _id in r.inserted_ids]
            return inserted_ids
        except PyMongoError as e:
            return f"Error inserting into the database: {e}"

    def get_trip_by_id(self, id: str)->Union[Trip,str]:
        try:
            result = self.collection.find_one({"_id": ObjectId(id)})
            result["_id"]=str(result["_id"])
            result["id"]=result["_id"]
            result.pop("_id")
            castedResult=Trip(**result)
            return castedResult 
        except Exception as e:
            return f"Error fetching trip by id: {e}"

    def put_trip_by_doc_id(self, id: str, trip: Trip):
        try:
            update_result = self.collection.update_one(
                {"_id": ObjectId(id)},
                {"$set": trip.model_dump()}
            )
            return update_result.modified_count > 0
        except Exception as e:
            return f"Error updating trip: {e}"

    def delete_place_from_trip(self, trip_id: str, place_id: str):
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(trip_id)},
                {"$pull": {"days.$[].places": {"placeId": place_id}}}
            )
            return result.modified_count > 0
        except Exception as e:
            return f"Error deleting place from trip: {e}"
        result = self.collection.update_one(
            {"_id": ObjectId(trip_id)},
            {"$pull": {"days.$[].places": {"placeId": place_id}}},
        )
        return result.modified_count > 0

    def get_all_trips(self):
        result = list(self.collection.find({}))
        parsed_documents = [{**doc, "_id": str(doc["_id"])} for doc in result]
        return parsed_documents
    
    def get_trip_by_id(self, id: str):  
        result = self.collection.find_one({"_id": ObjectId(id)})
        if result:
            result["_id"] = str(result["_id"])
        return result
