import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_TOKEN = "8054026412:AAGufbUub71R2lxsZrbrp1wYmC7VQht5A9c"
BOT_USERNAME = "zo_builder_bot"

# GitHub configuration
GITHUB_REPO = os.getenv("GITHUB_REPO", "organization/zo-house")

# MongoDB configuration
MONGODB_URI = "mongodb+srv://kshitij:DpBYFpgm1WIFPfwO@cluster0.svflpiw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
MONGODB_DB = os.getenv("MONGODB_DB", "zo_house_bot")

# Builder Score configuration
SCORE_WEIGHTS = {
    "github_commit": 2,
    "github_pr": 5,
    "github_issue": 1,
    "project_submission": 10,
    "nomination": 3,
}
