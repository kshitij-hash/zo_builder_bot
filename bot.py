#!/usr/bin/env python
import datetime
import logging
import os
from urllib.parse import urlencode

import requests
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

import database
from config import (
    BOT_USERNAME,
    CALLBACK_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    TELEGRAM_TOKEN,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
GITHUB_USERNAME, WALLET_ADDRESS, GITHUB_AUTH = range(3)


def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    print(user)
    database.get_or_create_user(user.id, user.username, user.first_name)

    # Check if user is new or returning
    user_data = database.get_user(user.id)
    is_new_user = not (
        user_data.get("github_username") or user_data.get("wallet_address")
    )

    welcome_message = (
        f"Hi *{user.first_name}!* 🎉\n\n"
        f"Welcome to Zo House Builder Bot! I help track projects, contribute to Zo House, and earn rewards as a builder.\n\n"
        f"To get started:\n"
        f"1️⃣ Connect your GitHub & wallet\n"
        f"2️⃣ Star our GitHub repo at github.com/zohouse\n"
        f"3️⃣ Check out featured projects with /projects\n"
        f"Use /help to see all available commands."
    )

    # Create onboarding keyboard for new users
    keyboard = [
        [
            InlineKeyboardButton("Connect GitHub", callback_data="setup_github"),
            InlineKeyboardButton("Link Wallet", callback_data="link_wallet"),
        ],
        [
            InlineKeyboardButton(
                "⭐️ Star Zo House Repo", url="https://github.com/zohouse"
            ),
            InlineKeyboardButton("View Projects", callback_data="view_projects"),
        ],
        [
            InlineKeyboardButton("How to Contribute", callback_data="show_contribute"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        welcome_message, reply_markup=reply_markup, parse_mode="Markdown"
    )

    # Send follow-up message after 2 seconds with additional information
    if is_new_user:
        context.job_queue.run_once(
            send_onboarding_tips,
            2,  # 2 seconds delay
            context={"chat_id": update.effective_chat.id, "user_name": user.first_name},
        )


def send_onboarding_tips(context: CallbackContext) -> None:
    """Send additional onboarding tips after initial greeting"""
    chat_id = context.job.context["chat_id"]
    user_name = context.job.context["user_name"]

    tips_text = (
        f"*Quick tip, {user_name}!* 👋\n\n"
        f"Connecting your GitHub account allows me to:\n"
        f"• Track your contributions automatically\n"
        f"• Award you builder points\n"
        f"• Include you in community rewards\n\n"
        f"Connect now to get started!"
    )

    keyboard = [
        [InlineKeyboardButton("Connect GitHub Now", callback_data="setup_github")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(
        chat_id=chat_id,
        text=tips_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "🤖 *Zo House Builder Bot Commands* 🤖\n\n"
        "*General Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n\n"
        "*Profile & Scores:*\n"
        "/profile - View your builder profile\n"
        "/score - Check your builder score\n"
        "/linkgithub - Connect your GitHub account\n"
        "/linkwallet - Connect your crypto wallet\n\n"
        "*Projects & Building:*\n"
        "/projects - Browse featured projects\n"
        "/contribute - See contribution opportunities\n"
        "/submit - Submit a new project\n"
        "/nominate - Nominate a builder for recognition\n\n"
        "*Community:*\n"
        "/leaderboard - View top builders\n"
        "/recap - See weekly community recap\n\n"
        "For admin commands, use /adminhelp"
    )
    update.message.reply_text(help_text, parse_mode="Markdown")


def profile_command(update: Update, context: CallbackContext) -> None:
    """Show the user's profile information."""
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    if not user_data:
        update.message.reply_text(
            "You don't have a profile yet. Use /start to set one up!"
        )
        return

    # Format profile information
    github_username = user_data.get("github_username", "Not linked")
    github_profile_url = user_data.get("github_info", {}).get("profile_url", None)
    github_repos = user_data.get("github_info", {}).get("public_repos", 0)
    github_followers = user_data.get("github_info", {}).get("followers", 0)
    wallet_address = user_data.get("wallet_address", "Not linked")
    builder_score = user_data.get("builder_score", 0)

    # Format wallet address display with null check
    wallet_display = (
        wallet_address[:8] + "..."
        if isinstance(wallet_address, str) and len(wallet_address) > 10
        else wallet_address
    )

    # Format GitHub information - avoid Markdown link issues
    if github_username != "Not linked" and github_profile_url:
        # Display username and URL separately to avoid Markdown parsing issues
        github_display = f"{github_username}"
        github_url_info = f"Profile: {github_profile_url}"
        github_stats = f"Repos: {github_repos} | Followers: {github_followers}"
    else:
        github_display = github_username
        github_url_info = ""
        github_stats = ""

    # Build profile text without problematic Markdown formatting
    profile_text = (
        f"🏗️ Builder Profile 🏗️\n\n"
        f"Username: @{update.effective_user.username or 'Not set'}\n"
        f"Builder Score: {builder_score} points\n"
        f"GitHub: {github_display}\n"
    )

    # Add GitHub URL if available
    if github_url_info:
        profile_text += f"{github_url_info}\n"

    # Add GitHub stats if available
    if github_stats:
        profile_text += f"{github_stats}\n"

    profile_text += (
        f"Wallet: {wallet_display}\n\nUse /score to see your score breakdown."
    )

    keyboard = [
        [
            InlineKeyboardButton("Update GitHub", callback_data="setup_github"),
            InlineKeyboardButton("Update Wallet", callback_data="link_wallet"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use HTML instead of Markdown for safer parsing
    update.message.reply_text(
        profile_text,
        reply_markup=reply_markup,
        parse_mode=None,  # Disable Markdown parsing for now
    )


def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    query.answer()

    if query.data == "setup_github":
        # Store user_id in context for later use with the callback
        context.user_data["github_auth_pending"] = True

        # Generate GitHub OAuth URL - fixed syntax
        params = urlencode(
            {
                "client_id": GITHUB_CLIENT_ID,
                "redirect_uri": f"{CALLBACK_URL}/github_callback",  # Ensure this matches what's registered
                "scope": "read:user",
                "state": str(update.effective_user.id),
            }
        )
        auth_url = f"https://github.com/login/oauth/authorize?{params}"

        keyboard = [[InlineKeyboardButton("Connect GitHub", url=auth_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            text="Please connect your GitHub account by clicking the button below:",
            reply_markup=reply_markup,
        )
        return GITHUB_AUTH

    elif query.data == "link_wallet":
        query.edit_message_text(
            text="Please send your wallet address to link it to your profile."
        )
        return WALLET_ADDRESS

    elif query.data == "view_projects":
        query.edit_message_text(
            text="Here are the featured projects from Zo House community:\n\n"
            "(Project listing feature coming soon!)"
            "⭐️ Don't forget to star our GitHub repository to stay updated!"
        )

    elif query.data == "show_contribute":
        contribute_text = (
            "🔨 *How to Contribute to Zo House* 🔨\n\n"
            "Here are ways to start contributing:\n\n"
            "1️⃣ Star our repository\n"
            "2️⃣ Follow us on GitHub\n"
            "3️⃣ Check out open issues and start contributing\n"
            "4️⃣ Share and nominate other builders\n\n"
            "⭐️ Don't forget to star our GitHub repository to stay updated!"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "View GitHub Issues", url="https://github.com/zohouse/issues"
                )
            ],
            [InlineKeyboardButton("Back", callback_data="back_to_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            text=contribute_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    elif query.data == "back_to_menu":
        # Return to main menu
        welcome_message = (
            f"Zo House Builder Bot! 👋\n\n"
            f"What would you like to do?\n\n"
            f"Use these commands to navigate:\n"
            f"- /profile - View your builder profile\n"
            f"- /projects - Browse featured projects\n"
            f"- /help - Show all available commands\n\n"
        )

        keyboard = [
            [
                InlineKeyboardButton("My Profile", callback_data="view_profile"),
                InlineKeyboardButton(
                    "Featured Projects", callback_data="view_projects"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⭐️ Star Zo House Repo", url="https://github.com/zohouse"
                ),
                InlineKeyboardButton(
                    "How to Contribute", callback_data="show_contribute"
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        query.edit_message_text(
            text=welcome_message, reply_markup=reply_markup, parse_mode="Markdown"
        )


def github_auth_callback(request):
    """Handle GitHub OAuth callback from the web server."""
    code = request.args.get("code")
    user_id = request.args.get("state")

    print(f"GitHub OAuth callback received - code: {code}, user_id: {user_id}")

    if not code or not user_id:
        print("Authentication failed: Missing code or user_id")
        return "Authentication failed. Missing parameters."

    # Exchange code for access token
    token_url = "https://github.com/login/oauth/access_token"
    token_data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": f"{CALLBACK_URL}/github_callback",  # MUST match exactly what's registered in GitHub
    }

    print(f"Sending token request to GitHub with data: {token_data}")
    try:
        response = requests.post(
            token_url,
            data=token_data,
            headers={"Accept": "application/json"},
        )
        print(f"Token response status: {response.status_code}")
        print(f"Token response content: {response.text}")
        if response.status_code == 200:
            try:
                data = response.json()
                access_token = data.get("access_token")
                if not access_token:
                    print(f"No access token in response: {data}")
                    return (
                        "Authentication failed: No access token returned from GitHub."
                    )

                # Get GitHub user info
                user_response = requests.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"token {access_token}",
                        "Accept": "application/json",
                    },
                )
                print(f"GitHub API response status: {user_response.status_code}")
                print(f"GitHub API response: {user_response.text}")
                if user_response.status_code == 200:
                    github_data = user_response.json()
                    github_username = github_data.get("login")

                    # Extract additional GitHub profile information
                    github_info = {
                        "username": github_username,
                        "profile_url": github_data.get("html_url"),
                        "avatar_url": github_data.get("avatar_url"),
                        "name": github_data.get("name"),
                        "bio": github_data.get("bio"),
                        "public_repos": github_data.get("public_repos", 0),
                        "followers": github_data.get("followers", 0),
                        "created_at": github_data.get("created_at"),
                    }

                    # Update user in database with extended GitHub info
                    database.update_user_github(
                        int(user_id),
                        github_username,
                        access_token,
                        github_info=github_info,
                    )

                    # Send message to user via bot
                    try:
                        bot = Bot(TELEGRAM_TOKEN)
                        bot.send_message(
                            chat_id=user_id,
                            text=f"✅ Successfully connected your GitHub account: {github_username}",
                        )
                    except Exception as e:
                        print(f"Error sending Telegram message: {e}")
                    return "GitHub account successfully connected! You can close this window and return to the bot."
                else:
                    print(f"GitHub API error: {user_response.text}")
                    return f"Authentication failed: Unable to get GitHub user information. Status code: {user_response.status_code}"
            except Exception as e:
                print(f"JSON parsing error: {e}")
                return (
                    f"Authentication failed: Unable to parse response from GitHub: {e}"
                )
        else:
            print(f"Token exchange failed: {response.text}")
            return f"Authentication failed: Unable to exchange code for token. Status code: {response.status_code}"
    except Exception as e:
        print(f"Request exception: {e}")
        return f"Authentication failed: {str(e)}"


def save_github_username(update: Update, context: CallbackContext) -> int:
    """Legacy function for manually saving GitHub username. Only used as fallback now."""
    user_id = update.effective_user.id
    github_username = update.message.text
    # Store username but mark as unverified
    database.update_user_github(user_id, github_username, verified=False)
    update.message.reply_text(
        f"I've saved {github_username} as your GitHub username.\n\n"
        f"For full GitHub integration, use the /linkgithub command to authenticate."
    )
    return ConversationHandler.END


def save_wallet_address(update: Update, context: CallbackContext) -> int:
    """Save wallet address and end the conversation."""
    user_id = update.effective_user.id
    wallet_address = update.message.text
    # Here you would verify if the wallet address is valid
    # For now, we'll just store it
    database.update_user_wallet(user_id, wallet_address)
    update.message.reply_text(
        f"Great! Your wallet has been linked.\n\n"
        f"Your builder rewards will be associated with this address."
    )
    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


def projects_command(update: Update, context: CallbackContext) -> None:
    """Show featured projects."""
    update.message.reply_text(
        "🚀 *Featured Zo House Projects* 🚀\n\n"
        "Here are some highlighted projects from our community:\n\n"
        "• *Project listings coming soon*\n\n"
        "Want to add your project? Use the /submit command!",
        parse_mode="Markdown",
    )


def contribute_command(update: Update, context: CallbackContext) -> None:
    """Show contribution opportunities."""
    update.message.reply_text(
        "🔨 *How to Contribute to Zo House* 🔨\n\n"
        "Looking to get involved? Here are some ways:\n\n"
        "1️⃣ Star our GitHub repo: [Zo House GitHub](https://github.com/zohouse)\n"
        "2️⃣ Check open issues and start contributing\n"
        "3️⃣ Share your own projects with the community\n"
        "4️⃣ Nominate and support other builders\n\n"
        "Your contributions will increase your Builder Score!",
        parse_mode="Markdown",
    )


def linkgithub_command(update: Update, context: CallbackContext) -> None:
    """Command to initiate GitHub linking process."""
    user_id = update.effective_user.id

    # Fixed syntax for generating GitHub OAuth URL
    params = urlencode(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": f"{CALLBACK_URL}/github_callback",
            "scope": "read:user",
            "state": str(user_id),
        }
    )
    auth_url = f"https://github.com/login/oauth/authorize?{params}"

    keyboard = [[InlineKeyboardButton("Connect GitHub", url=auth_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "Connect your GitHub account to verify your contributions and earn builder points!",
        reply_markup=reply_markup,
    )


def setup_reminders(updater):
    """Setup periodic engagement reminders"""
    # Schedule daily GitHub engagement reminder at 10:00 AM
    updater.job_queue.run_daily(
        send_github_engagement_reminder,
        datetime.time(hour=10, minute=0, second=0),
    )


def send_github_engagement_reminder(context: CallbackContext):
    """Send periodic reminders to engage with GitHub"""
    # Get all users from database who haven't starred the repo
    # In a real implementation, you'd check GitHub API for this
    try:
        users = database.get_all_users()
        for user in users:
            try:
                if not user.get(
                    "github_star_check", False
                ):  # Using this as placeholder
                    reminder_text = (
                        f"Hey {user['first_name']}! 👋\n\n"
                        f"Have you checked out the Zo House GitHub repository lately?\n\n"
                        f"Starring our repo helps you:\n"
                        f"• Stay updated with new projects\n"
                        f"• Track your contributions\n"
                        f"• Support the community's growth\n\n"
                        f"Take a second! 🚀"
                    )

                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "⭐️ Star Now", url="https://github.com/zohouse"
                            )
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    context.bot.send_message(
                        chat_id=user["user_id"],
                        text=reminder_text,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
            except Exception as e:
                print(f"Error sending reminder to user {user['user_id']}: {e}")
    except Exception as e:
        print(f"Error in GitHub engagement reminder: {e}")


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(TELEGRAM_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Basic command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("profile", profile_command))
    dispatcher.add_handler(CommandHandler("projects", projects_command))
    dispatcher.add_handler(CommandHandler("contribute", contribute_command))
    dispatcher.add_handler(CommandHandler("linkgithub", linkgithub_command))

    # Setup conversation handlers for GitHub and wallet setup
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                button_callback, pattern="^(setup_github|link_wallet)$"
            )
        ],
        states={
            GITHUB_USERNAME: [
                MessageHandler(Filters.text & ~Filters.command, save_github_username)
            ],
            WALLET_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, save_wallet_address)
            ],
            GITHUB_AUTH: [
                # This state just waits for OAuth callback which is handled separately
                MessageHandler(
                    Filters.text & ~Filters.command,
                    lambda u, c: ConversationHandler.END,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(conv_handler)

    # Handle other button callbacks
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    # Set up periodic reminders
    setup_reminders(updater)

    # Start the Bot
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
