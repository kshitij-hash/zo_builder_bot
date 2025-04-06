import datetime

import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from config import MONGODB_DB, MONGODB_URI

# Initialize MongoDB connection with error handling
try:
    # Create a new client with ServerApi v1 for MongoDB Atlas
    print(MONGODB_URI)
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


def get_or_create_user(user_id, username=None, first_name=None):
    """Get a user document or create it if it doesn't exist."""
    user = users_collection.find_one({"user_id": user_id})

    if not user:
        user = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "github_username": None,
            "wallet_address": None,
            "builder_score": 0,
            "telegram_activity": {
                "messages": 0,
                "replies": 0,
            },
            "github_contributions": {
                "commits": 0,
                "prs": 0,
                "issues": 0,
            },
            "created_at": datetime.datetime.now(),
        }
        users_collection.insert_one(user)
        return user, True  # Return user and True to indicate this is a new user

    return user, False  # Return user and False to indicate not a new user


def get_user(user_id):
    """Get a user document by Telegram user ID."""
    return users_collection.find_one({"user_id": user_id})


def update_user_github(user_id, github_username):
    """Update user's GitHub username in the database."""
    result = users_collection.update_one(
        {"user_id": user_id}, {"$set": {"github_username": github_username}}
    )
    return result.modified_count > 0


def update_user_wallet(user_id, wallet_address):
    """Update a user's wallet address."""
    return users_collection.update_one(
        {"user_id": user_id}, {"$set": {"wallet_address": wallet_address}}
    )



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


def get_all_users():
    """Get all users from the database"""
    try:
        users = list(users_collection.find({}, {"_id": 0}))
        return users
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []


def update_telegram_activity(user_id, activity_type):
    """
    Update a user's Telegram activity metrics.

    Args:
        user_id (int): The Telegram user ID
        activity_type (str): One of 'messages', 'replies'

    Returns:
        bool: True if update was successful, False otherwise
    """
    if activity_type not in ["messages", "replies"]:
        print(f"Invalid activity type: {activity_type}")
        return False

    # Update the specific activity count
    update_field = f"telegram_activity.{activity_type}"
    result = users_collection.update_one(
        {"user_id": user_id}, {"$inc": {update_field: 1}}
    )

    return result.modified_count > 0


def get_user_by_github_username(github_username):
    """Get a user document by GitHub username."""
    return users_collection.find_one({"github_username": github_username})


def update_github_contribution(github_username, contribution_type):
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


def update_user_builder_score(user_id, score):
    """
    Update a user's builder score.

    Args:
        user_id (int): The Telegram user ID
        score (float): The new builder score

    Returns:
        bool: True if update was successful, False otherwise
    """
    result = users_collection.update_one(
        {"user_id": user_id}, {"$set": {"builder_score": score}}
    )
    return result.modified_count > 0
