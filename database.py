from typing import Any, Dict, List, Optional
import datetime

import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from config import MONGODB_DB, MONGODB_URI

# Initialize MongoDB connection with error handling
try:
    # Create a new client with ServerApi v1 for MongoDB Atlas
    client = MongoClient(MONGODB_URI, server_api=ServerApi("1"))

    # Verify connection with ping command
    client.admin.command("ping")
    print("Pinged your deployment. You successfully connected to MongoDB!")
except pymongo.errors.ConfigurationError as e:
    print(f"MongoDB Connection Error: {e}")
    print("Please check your MONGODB_URI in .env file or environment variables")
    print("Make sure you have installed pymongo[srv] with: pip install 'pymongo[srv]'")
    raise
except pymongo.errors.ConnectionFailure as e:
    print(f"Failed to connect to MongoDB: {e}")
    raise
except Exception as e:
    print(f"Unexpected error with MongoDB connection: {e}")
    raise

db = client[MONGODB_DB]
users_collection = db["users"]
projects_collection = db["projects"]
activities_collection = db["activities"]


def get_or_create_user(
    user_id: int, username: Optional[str], first_name: str
) -> Dict[str, Any]:
    """Get existing user or create a new one"""
    user = users_collection.find_one({"user_id": user_id})
    
    if not user:
        user = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "github_username": None,
            "wallet_address": None,
            "builder_score": 0,
            "github_contributions": {"commits": 0, "prs": 0, "issues": 0},
            "telegram_activity": {"messages": 0, "replies": 0},
            "nominations_received": 0,
            "nominations_given": [],
            "created_at": datetime.datetime.now(),
        }
        users_collection.insert_one(user)
    
    return user


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    return users_collection.find_one({"user_id": user_id})


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by Telegram username"""
    return users_collection.find_one({"username": username})


def get_all_users() -> List[Dict[str, Any]]:
    """Get all users"""
    try:
        return list(users_collection.find({}, {"_id": 0}))
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []


def update_user_github(user_id: int, github_username: str) -> bool:
    """Update user's GitHub username"""
    result = users_collection.update_one(
        {"user_id": user_id}, {"$set": {"github_username": github_username}}
    )
    return result.modified_count > 0


def update_user_wallet(user_id: int, wallet_address: str) -> bool:
    """Update user's wallet address"""
    result = users_collection.update_one(
        {"user_id": user_id}, {"$set": {"wallet_address": wallet_address}}
    )
    return result.modified_count > 0


def update_telegram_activity(user_id: int, activity_type: str) -> bool:
    """Update user's Telegram activity"""
    if activity_type not in ["messages", "replies"]:
        print(f"Invalid activity type: {activity_type}")
        return False
    
    # Update the specific activity count
    update_field = f"telegram_activity.{activity_type}"
    result = users_collection.update_one(
        {"user_id": user_id}, {"$inc": {update_field: 1}}
    )
    
    return result.modified_count > 0


def update_user_builder_score(user_id: int, score: float) -> bool:
    """Update user's builder score"""
    result = users_collection.update_one(
        {"user_id": user_id}, {"$set": {"builder_score": score}}
    )
    return result.modified_count > 0


def add_nomination(nominator_id: int, nominee_username: str) -> dict:
    """
    Add a nomination from one user to another.

    Args:
        nominator_id: User ID of the nominator
        nominee_username: Username of the person being nominated

    Returns:
        dict: Result with status, message and nominee data if successful
    """
    # Check if nominator exists
    nominator = users_collection.find_one({"user_id": nominator_id})
    if not nominator:
        return {
            "status": "error",
            "message": "You must set up your profile before nominating others",
        }

    # Find nominee by username
    nominee = users_collection.find_one({"username": nominee_username})

    # If nominee not found
    if not nominee:
        return {
            "status": "error",
            "message": f"User @{nominee_username} not found. Make sure they have set up their profile.",
        }

    # Check if nominating self
    if nominator_id == nominee["user_id"]:
        return {"status": "error", "message": "You cannot nominate yourself"}

    # Check if already nominated this user
    nominations_given = nominator.get("nominations_given", [])
    if nominee_username in nominations_given:
        return {
            "status": "error",
            "message": f"You have already nominated @{nominee_username}",
        }

    # Add nomination
    users_collection.update_one(
        {"user_id": nominator_id},
        {"$push": {"nominations_given": nominee_username}}
    )

    users_collection.update_one(
        {"user_id": nominee["user_id"]},
        {"$inc": {"nominations_received": 1}}
    )

    # Get updated nominee data
    updated_nominee = users_collection.find_one({"username": nominee_username})

    return {
        "status": "success",
        "message": f"You have successfully nominated @{nominee_username}",
        "nominee": updated_nominee,
    }


def get_user_by_github_username(github_username: str) -> Optional[Dict[str, Any]]:
    """Get a user document by GitHub username."""
    return users_collection.find_one({"github_username": github_username})


def update_github_contribution(github_username: str, contribution_type: str) -> bool:
    """
    Update a user's GitHub contributions count.

    Args:
        github_username (str): The GitHub username
        contribution_type (str): One of 'commits', 'prs', or 'issues'

    Returns:
        bool: True if user was found and updated, False otherwise
    """
    if contribution_type not in ["commits", "prs", "issues"]:
        print(f"Invalid contribution type: {contribution_type}")
        return False

    # Find user by GitHub username
    user = get_user_by_github_username(github_username)
    if not user:
        print(f"No user found with GitHub username: {github_username}")
        return False

    # Update the specific contribution count
    update_field = f"github_contributions.{contribution_type}"
    result = users_collection.update_one(
        {"github_username": github_username}, {"$inc": {update_field: 1}}
    )

    return result.modified_count > 0


def get_top_builders(limit=10):
    """Get the top builders by score."""
    return list(users_collection.find().sort("builder_score", -1).limit(limit))


def save_project(project_data):
    """Save a project to the database."""
    project_data["created_at"] = datetime.datetime.now()
    return projects_collection.insert_one(project_data)


def get_projects(limit=10):
    """Get the most recent projects."""
    return list(projects_collection.find().sort("created_at", -1).limit(limit))
