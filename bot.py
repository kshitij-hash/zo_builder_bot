#!/usr/bin/env python
import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
from config import TELEGRAM_TOKEN

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
GITHUB_USERNAME, WALLET_ADDRESS = range(2)


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
        f"1️⃣ Add your GitHub username & wallet\n"
        f"2️⃣ Follow our GitHub organization at https://github.com/zohouse\n"
        f"3️⃣ Check out featured projects with /projects\n"
        f"Use /help to see all available commands."
    )

    # Create onboarding keyboard showing only options that haven't been set
    keyboard = []

    # First row - GitHub and Wallet buttons (only if not already set)
    first_row = []
    if not user_data.get("github_username"):
        first_row.append(
            InlineKeyboardButton("Add GitHub Username", callback_data="setup_github")
        )
    if not user_data.get("wallet_address"):
        first_row.append(
            InlineKeyboardButton("Add Wallet Address", callback_data="link_wallet")
        )

    if first_row:
        keyboard.append(first_row)

    # Add other buttons that are always shown
    keyboard.append(
        [
            InlineKeyboardButton(
                "Follow Zo House Organization", url="https://github.com/zohouse"
            ),
            InlineKeyboardButton("View Projects", callback_data="view_projects"),
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton("How to Contribute", callback_data="show_contribute"),
        ]
    )

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

    # Check if user has already set GitHub username
    user_data = None
    try:
        user_data = database.get_user(chat_id)
    except Exception as e:
        print(f"Error getting user data: {e}")

    # If GitHub username is already set, don't suggest adding it
    if user_data and user_data.get("github_username"):
        return

    tips_text = (
        f"*Quick tip, {user_name}!* 👋\n\n"
        f"Adding your GitHub username allows me to:\n"
        f"• Track your contributions\n"
        f"• Award you builder points\n"
        f"• Include you in community rewards\n\n"
        f"Add it now to get started! (You won't be able to change it later)"
    )

    keyboard = [
        [InlineKeyboardButton("Add GitHub Username", callback_data="setup_github")]
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
        "/linkgithub - Add your GitHub username\n"
        "/linkwallet - Add your crypto wallet\n\n"
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
    github_username = user_data.get("github_username", "Not added")
    wallet_address = user_data.get("wallet_address", "Not added")
    builder_score = user_data.get("builder_score", 0)

    # Format wallet address display with null check
    wallet_display = (
        wallet_address[:8] + "..."
        if isinstance(wallet_address, str) and len(wallet_address) > 10
        else wallet_address
    )

    # Build profile text
    profile_text = (
        f"🏗️ Builder Profile 🏗️\n\n"
        f"Username: @{update.effective_user.username or 'Not set'}\n"
        f"Builder Score: {builder_score} points\n"
        f"GitHub: {github_username}\n"
        f"Wallet: {wallet_display}\n\nUse /score to see your score breakdown."
    )

    # Only show buttons for fields that haven't been set
    keyboard = []

    if github_username == "Not added":
        keyboard.append(
            [InlineKeyboardButton("Add GitHub Username", callback_data="setup_github")]
        )

    if wallet_address == "Not added":
        keyboard.append(
            [InlineKeyboardButton("Add Wallet Address", callback_data="link_wallet")]
        )

    # Only add reply_markup if there are buttons to show
    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(profile_text, reply_markup=reply_markup)
    else:
        update.message.reply_text(profile_text)


def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    query.answer()

    if query.data == "setup_github":
        # Check if GitHub username is already set
        user_id = update.effective_user.id
        user_data = database.get_user(user_id)

        if user_data and user_data.get("github_username"):
            query.edit_message_text(
                text="Your GitHub username is already set and cannot be changed."
            )
            return ConversationHandler.END

        query.edit_message_text(text="Please enter your GitHub username:")
        return GITHUB_USERNAME

    elif query.data == "link_wallet":
        # Check if wallet address is already set
        user_id = update.effective_user.id
        user_data = database.get_user(user_id)

        if user_data and user_data.get("wallet_address"):
            query.edit_message_text(
                text="Your wallet address is already set and cannot be changed."
            )
            return ConversationHandler.END

        query.edit_message_text(
            text="Please send your wallet address to link it to your profile."
        )
        return WALLET_ADDRESS

    elif query.data == "view_projects":
        query.edit_message_text(
            text="Here are the featured projects from Zo House community:\n\n"
            "(Project listing feature coming soon!)"
            "Don't forget to follow our GitHub organization to stay updated!"
        )

    elif query.data == "show_contribute":
        contribute_text = (
            "🔨 *How to Contribute to Zo House* 🔨\n\n"
            "Here are ways to start contributing:\n\n"
            "1️⃣ Follow our GitHub organization\n"
            "2️⃣ Check out open issues and start contributing\n"
            "3️⃣ Share and nominate other builders\n\n"
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
            "Zo House Builder Bot! 👋\n\n"
            "What would you like to do?\n\n"
            "Use these commands to navigate:\n"
            "- /profile - View your builder profile\n"
            "- /projects - Browse featured projects\n"
            "- /help - Show all available commands\n\n"
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


def save_github_username(update: Update, context: CallbackContext) -> int:
    """Save GitHub username and end the conversation."""
    user_id = update.effective_user.id
    github_username = update.message.text

    # Check if username is already set
    user_data = database.get_user(user_id)
    if user_data and user_data.get("github_username"):
        update.message.reply_text(
            "Your GitHub username is already set and cannot be changed."
        )
        return ConversationHandler.END

    # Simply store the username without verification
    database.update_user_github(user_id, github_username)

    update.message.reply_text(
        f"Great! I've saved '{github_username}' as your GitHub username.\n\n"
        f"Please note that this cannot be changed later.\n\n"
        f"Now you can track your contributions and earn builder points!"
    )
    return ConversationHandler.END


def save_wallet_address(update: Update, context: CallbackContext) -> int:
    """Save wallet address and end the conversation."""
    user_id = update.effective_user.id
    wallet_address = update.message.text

    # Check if wallet is already set
    user_data = database.get_user(user_id)
    if user_data and user_data.get("wallet_address"):
        update.message.reply_text(
            "Your wallet address is already set and cannot be changed."
        )
        return ConversationHandler.END

    # Just store the wallet address without verification
    database.update_user_wallet(user_id, wallet_address)

    update.message.reply_text(
        "Great! Your wallet has been linked.\n\n"
        "Please note that this cannot be changed later.\n\n"
        "Your builder rewards will be associated with this address."
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
        "1️⃣ Follow our GitHub organization: [Zo House GitHub](https://github.com/zohouse)\n"
        "2️⃣ Check open issues and start contributing\n"
        "3️⃣ Share your own projects with the community\n"
        "4️⃣ Nominate and support other builders\n\n"
        "Your contributions will increase your Builder Score!",
        parse_mode="Markdown",
    )


def linkgithub_command(update: Update, context: CallbackContext) -> None:
    """Command to initiate GitHub username collection."""
    # Check if GitHub username is already set
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    if user_data and user_data.get("github_username"):
        update.message.reply_text(
            f"Your GitHub username is already set to '{user_data.get('github_username')}' and cannot be changed."
        )
        return ConversationHandler.END

    update.message.reply_text("Please enter your GitHub username:")
    return GITHUB_USERNAME


def linkwallet_command(update: Update, context: CallbackContext) -> None:
    """Command to initiate wallet address collection."""
    # Check if wallet address is already set
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    if user_data and user_data.get("wallet_address"):
        wallet = user_data.get("wallet_address")
        # Format for display if long
        if isinstance(wallet, str) and len(wallet) > 10:
            wallet_display = wallet[:8] + "..."
        else:
            wallet_display = wallet

        update.message.reply_text(
            f"Your wallet address is already set to '{wallet_display}' and cannot be changed."
        )
        return ConversationHandler.END

    update.message.reply_text("Please enter your wallet address:")
    return WALLET_ADDRESS


def setup_reminders(updater):
    """Setup periodic engagement reminders"""
    # Schedule daily GitHub engagement reminder at 10:00 AM
    updater.job_queue.run_daily(
        send_github_engagement_reminder,
        datetime.time(hour=10, minute=0, second=0),
    )


def send_github_engagement_reminder(context: CallbackContext):
    """Send periodic reminders to engage with GitHub"""
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

    # Setup direct command handlers for GitHub and wallet info
    github_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("linkgithub", linkgithub_command)],
        states={
            GITHUB_USERNAME: [
                MessageHandler(Filters.text & ~Filters.command, save_github_username)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    wallet_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("linkwallet", linkwallet_command)],
        states={
            WALLET_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, save_wallet_address)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    dispatcher.add_handler(github_conv_handler)
    dispatcher.add_handler(wallet_conv_handler)

    # Setup conversation handlers for button callbacks
    button_conv_handler = ConversationHandler(
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
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(button_conv_handler)

    # Handle other button callbacks
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    # Set up periodic reminders
    setup_reminders(updater)

    # Start the Bot
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
