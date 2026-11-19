import logging
from typing import Optional
from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from pymongo.collection import Collection

from ..config import Config

logger = logging.getLogger("ResearchLens.MongoDB")

_mongo_client: Optional[MongoClient] = None
_mongo_db: Optional[Database] = None


def get_mongo_client() -> MongoClient:
    """Returns a singleton PyMongo client instance."""
    global _mongo_client
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(
                Config.MONGODB_URI,
                serverSelectionTimeoutMS=4000,
                connectTimeoutMS=4000
            )
            # Ping database to verify connection
            _mongo_client.admin.command('ping')
            logger.info(f"Connected to MongoDB at {Config.MONGODB_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB at {Config.MONGODB_URI}: {e}")
            raise e
    return _mongo_client


def get_db() -> Database:
    """Returns the ResearchLens database instance."""
    global _mongo_db
    if _mongo_db is None:
        client = get_mongo_client()
        _mongo_db = client[Config.MONGODB_DB_NAME]
    return _mongo_db


# Primary Collections
def get_users_collection() -> Collection:
    return get_db()["users"]


def get_documents_collection() -> Collection:
    return get_db()["documents"]


def get_reports_collection() -> Collection:
    return get_db()["reports"]


def get_configurations_collection() -> Collection:
    return get_db()["configurations"]


def get_projects_collection() -> Collection:
    return get_db()["projects"]


def get_crawled_pages_collection() -> Collection:
    return get_db()["crawled_pages"]


def init_mongo() -> None:
    """Initializes MongoDB indices for users, documents, reports, and configurations."""
    try:
        db = get_db()
        # Users indices
        db["users"].create_index([("username", ASCENDING)], unique=True)
        db["users"].create_index([("email", ASCENDING)], unique=True)

        # Documents indices
        db["documents"].create_index([("project_id", ASCENDING)])
        db["documents"].create_index([("user_id", ASCENDING)])

        # Reports indices
        db["reports"].create_index([("project_id", ASCENDING)])
        db["reports"].create_index([("user_id", ASCENDING)])

        # Configurations indices
        db["configurations"].create_index([("project_id", ASCENDING)])
        db["configurations"].create_index([("user_id", ASCENDING)])

        # Projects indices
        db["projects"].create_index([("user_id", ASCENDING)])
        db["projects"].create_index([("created_at", ASCENDING)])

        # Crawled pages indices
        db["crawled_pages"].create_index([("project_id", ASCENDING)])

        logger.info(f"MongoDB indices initialized for database: {Config.MONGODB_DB_NAME}")
    except Exception as e:
        logger.error(f"Error initializing MongoDB: {e}")
