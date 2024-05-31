from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# MongoDB Config
client = MongoClient(os.getenv("MONGO_URI"))
db = client["salesBot"]
