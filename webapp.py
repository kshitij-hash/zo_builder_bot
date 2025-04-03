from flask import Flask, request, redirect
import os
from telegram import Bot

from config import TELEGRAM_TOKEN
from bot import github_auth_callback

app = Flask(__name__)


@app.route("/")
def home():
    """Home page."""
    return "Welcome to the GitHub OAuth Integration!"


@app.route("/github_callback")
def github_callback():
    """Handle GitHub OAuth callback."""
    print("GitHub callback received!")
    print(f"Request args: {request.args}")
    print(f"Request headers: {request.headers}")
    
    return github_auth_callback(request)


if __name__ == "__main__":
    # Run the Flask app
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
