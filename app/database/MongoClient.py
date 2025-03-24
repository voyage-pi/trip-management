from pymongo import MongoClient as mongoDB
from dotenv import load_dotenv,dotenv_values
import os 

load_dotenv()


mongoHost= os.getenv("MONGO_HOST","mongo")
mongoPort= os.getenv("MONGO_PORT",27017)
mongoUser = os.getenv("MONGO_USER")
mongoPwd = os.getenv("MONGO_PASSWORD")
mongoDatabase = os.getenv("MONGO_DATABASE")

class MongoClient():
    def __init__(self):
        self.client=mongoDB(f"mongodb://{mongoUser}:{mongoPwd}@{mongoHost}:{mongoPort}/")
        self.current_database=None
        self.current_collection=None
    def use_db(self,db_name):
        self.current_database=self.client[db_name]
        return self
    def use_collection(self,collection_name):
        assert self.current_database != None
        self.current_collection= self.current_database[collection_name]
        return self


