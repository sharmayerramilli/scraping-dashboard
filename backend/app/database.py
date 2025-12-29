from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "scraping_dashboard")

# Async client for FastAPI
async_client = AsyncIOMotorClient(MONGODB_URL)
async_db = async_client[DATABASE_NAME]

# Sync client for workers
sync_client = MongoClient(MONGODB_URL)
sync_db = sync_client[DATABASE_NAME]

# Collections
# Zomato collections
zomato_jobs_collection = async_db["zomato_jobs"]
zomato_results_collection = async_db["zomato_results"]
zomato_failed_urls_collection = async_db["zomato_failed_urls"]

# Swiggy collections
swiggy_jobs_collection = async_db["swiggy_jobs"]
swiggy_results_collection = async_db["swiggy_results"]
swiggy_failed_urls_collection = async_db["swiggy_failed_urls"]

# Legacy collections (for backward compatibility)
jobs_collection = zomato_jobs_collection
results_collection = zomato_results_collection
failed_urls_collection = zomato_failed_urls_collection

# Sync collections for workers
# Zomato sync collections
sync_zomato_jobs_collection = sync_db["zomato_jobs"]
sync_zomato_results_collection = sync_db["zomato_results"]
sync_zomato_failed_urls_collection = sync_db["zomato_failed_urls"]

# Swiggy sync collections
sync_swiggy_jobs_collection = sync_db["swiggy_jobs"]
sync_swiggy_results_collection = sync_db["swiggy_results"]
sync_swiggy_failed_urls_collection = sync_db["swiggy_failed_urls"]

# Legacy sync collections (for backward compatibility)
sync_jobs_collection = sync_zomato_jobs_collection
sync_results_collection = sync_zomato_results_collection
sync_failed_urls_collection = sync_zomato_failed_urls_collection

async def close_db():
    async_client.close()
    sync_client.close()