import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update  # type: ignore
from telegram.ext import (  # type: ignore
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

import database
from builder_score import compute_builder_scores
from config import (
    TELEGRAM_TOKEN,
)

TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
GITHUB_USERNAME, WALLET_ADDRESS, RETURNING_TO_GROUP = range(3)

# Track which users are in profile setup and their originating group
user_setup_state = {}  # Format: {user_id: {'group_id': group_id, 'step': current_step}}

# Define group redirect message cache - will store message IDs for later deletion
group_message_cache = {}  # Format: {user_id: {'group_id': group_id, 'message_id': msg_id}}


# Function to check if chat is private
def is_private_chat(update):
    return update.effective_chat.type == "private"


def start_private_setup_flow(update: Update, context: CallbackContext) -> int:
    """Start the private setup flow with the user"""
    user = update.effective_user
    user_id = user.id

    # Get or create user
    database.get_or_create_user(user_id, user.username, user.first_name)

    # Then get the user data as a dictionary
    user_data = database.get_user(user_id)

    # Mark user as being in setup flow
    user_setup_state[user_id] = {"step": "start"}

    # Check if user already has a profile
    has_github = bool(user_data.get("github_username") if user_data else None)
    has_wallet = bool(user_data.get("wallet_address") if user_data else None)

    if has_github and has_wallet:
        # User already has full profile
        welcome_back_msg = (
            f"Welcome back, {escape_markdown_v2(user.first_name)}\\!\n\n"
            f"Your profile is already complete\\. You can use /profile to view it\\."
        )
        update.message.reply_text(welcome_back_msg, parse_mode="MarkdownV2")
        return ConversationHandler.END

    # Start the guided setup flow
    welcome_msg = (
        f"Hi {escape_markdown_v2(user.first_name)}\\! 👋\n\n"
        f"Let's set up your Zo House Builder profile\\. "
        f"This will only take a minute\\.\n\n"
    )

    if not has_github:
        welcome_msg += "Please enter your GitHub username to continue\\:"
        user_setup_state[user_id]["step"] = "github"
        print("User setup state:", user_setup_state)
        update.message.reply_text(welcome_msg, parse_mode="MarkdownV2")
        return GITHUB_USERNAME
    elif not has_wallet:
        welcome_msg += "Please enter your wallet address to complete your profile\\:"
        user_setup_state[user_id]["step"] = "wallet"
        update.message.reply_text(welcome_msg, parse_mode="MarkdownV2")
        return WALLET_ADDRESS

    return ConversationHandler.END


def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id

    # Create or get user in database - don't use the returned value directly
    database.get_or_create_user(user_id, user.username, user.first_name)

    # Check if this is a group chat
    if not is_private_chat(update):
        # Get user data to check if profile is complete
        user_data = database.get_user(user_id)
        has_github = bool(user_data.get("github_username") if user_data else None)
        has_wallet = bool(user_data.get("wallet_address") if user_data else None)
        
        # If profile is already complete, don't redirect to DM
        if has_github and has_wallet:
            update.message.reply_text(
                f"Hi {user.first_name}! Your builder profile is already set up. "
                f"You can use /profile to view it."
            )
            return
            
        # Remember originating group
        group_id = update.message.chat.id
        user_setup_state[user_id] = {"group_id": group_id, "step": "invited"}

        # Send message to group that we're moving to DM
        group_msg = (
            f"Hi {user.first_name}! "
            f"Let's set up your Zo House Builder profile in a private message. "
            f"I've sent you a DM to get started."
        )
        group_message = update.message.reply_text(group_msg)

        # Save message ID for potential cleanup later
        group_message_cache[user_id] = {
            "group_id": group_id,
            "message_id": group_message.message_id,
        }

        message = (
            f"Hi {user.first_name}! I'm Zo House Builder Bot. "
            f"Let's set up your profile here in private. "
        )
        keyboard = [
            [InlineKeyboardButton("Start Setup", callback_data="start_setup")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(
            user_id,
            text=message,
            reply_markup=reply_markup,
        )
        return

    # If we're already in a private chat, start the setup flow
    return start_private_setup_flow(update, context)


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

    # Escape user_name for MarkdownV2
    escaped_name = escape_markdown_v2(user_name)

    tips_text = (
        f"*Quick tip, {escaped_name}\\!* 👋\n\n"
        f"Adding your GitHub username allows me to:\n"
        f"• Track your contributions\n"
        f"• Award you builder points\n"
        f"• Include you in community rewards\n\n"
        f"Add it now to get started\\! \\(You won't be able to change it later\\)"
    )

    keyboard = [
        [InlineKeyboardButton("Add GitHub Username", callback_data="setup_github")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(
        chat_id=chat_id,
        text=tips_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2",
    )


def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "🤖 *Zo House Builder Bot Commands* 🤖\n\n"
        "*General Commands:*\n"
        "/start \\- Setup your profile\n"
        "/help \\- Show this help message\n\n"
        "*Profile & Scores:*\n"
        "/profile \\- View your builder profile\n"
        "/score \\- Check your builder score\n\n"
        "*Projects & Building:*\n"
        "/projects \\- Browse featured projects\n"
        "/contribute \\- See contribution opportunities\n"
        "/nominate \\- Nominate a builder for recognition \(ex: `/nominate username`\)\n\n"
        "*Community:*\n"
        "/leaderboard \\- View top builders\n"
    )
    update.message.reply_text(help_text, parse_mode="MarkdownV2")


def profile_command(update: Update, context: CallbackContext) -> None:
    """Show the user's profile information."""
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    if not user_data:
        # Check if we're in a group or private chat
        if not is_private_chat(update):
            # In group chat - redirect to DM
            group_id = update.effective_chat.id  # Fix: use effective_chat instead of chat
            user_setup_state[user_id] = {"group_id": group_id, "step": "invited"}

            group_msg = (
                f"Hi {update.effective_user.first_name}! "
                f"Please set up your profile in our private chat first."
            )
            update.message.reply_text(group_msg)

            # Send DM to user
            context.bot.send_message(
                user_id,
                f"Hi {update.effective_user.first_name}! Let's set up your Zo House Builder profile. "
                f"Type /start to begin.",
            )
        else:
            # In private chat - start setup
            update.message.reply_text(
                "You don't have a profile yet\\. Let's set one up\\!",
                parse_mode="MarkdownV2",
            )
            start_private_setup_flow(update, context)
        return

    # Format profile information
    github_username = user_data.get("github_username", "Not added")
    wallet_address = user_data.get("wallet_address", "Not added")
    builder_score = user_data.get("builder_score", 0)
    nominations_received = user_data.get("nominations_received", 0)

    # Format wallet address display with null check
    if isinstance(wallet_address, str) and len(wallet_address) > 10:
        wallet_display = wallet_address[:6] + "..." + wallet_address[-4:]
    else:
        wallet_display = wallet_address

    # Format builder_score for display and escape special characters
    if isinstance(builder_score, float):
        score_str = f"{builder_score:.2f}"
    else:
        score_str = str(builder_score)
    escaped_score = escape_markdown_v2(score_str)
    
    # Escape dynamic content for MarkdownV2
    escaped_username = escape_markdown_v2(update.effective_user.username or "Not set")
    escaped_github = escape_markdown_v2(github_username)
    escaped_wallet = escape_markdown_v2(str(wallet_display))
    escaped_nominations = escape_markdown_v2(str(nominations_received))

    # Build profile text
    profile_text = (
        f"🏗️ *Builder Profile* 🏗️\n\n"
        f"Username: @{escaped_username}\n"
        f"Builder Score: {escaped_score} points\n"
        f"GitHub: {escaped_github}\n"
        f"Wallet: {escaped_wallet}\n"
        f"Nominations received: {escaped_nominations}\n"
    )

    # Prompt to complete profile if needed
    missing_fields = []
    if github_username == "Not added":
        missing_fields.append("GitHub username")
    if wallet_address == "Not added":
        missing_fields.append("wallet address")

    if missing_fields and is_private_chat(update):
        profile_text += (
            "\n⚠️ Your profile is incomplete\\. Let's finish setting it up\\!"
        )
        update.message.reply_text(profile_text, parse_mode="MarkdownV2")
        return start_private_setup_flow(update, context)
    else:
        update.message.reply_text(profile_text, parse_mode="MarkdownV2")


def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    query.answer()

    if query.data == "start_setup":
        # Start the private setup flow
        user = update.effective_user
        user_id = user.id

        # Get or create user
        database.get_or_create_user(user_id, user.username, user.first_name)

        # Then get the user data as a dictionary
        user_data = database.get_user(user_id)

        # Mark user as being in setup flow
        user_setup_state[user_id] = {"step": "start"}

        # Check if user already has a profile
        has_github = bool(user_data.get("github_username") if user_data else None)
        has_wallet = bool(user_data.get("wallet_address") if user_data else None)

        if has_github and has_wallet:
            # User already has full profile
            welcome_back_msg = (
                f"Welcome back, {escape_markdown_v2(user.first_name)}\\!\n\n"
                f"Your profile is already complete\\. You can use /profile to view it\\."
            )
            query.edit_message_text(welcome_back_msg, parse_mode="MarkdownV2")
            return ConversationHandler.END

        # Start the guided setup flow
        welcome_msg = (
            f"Hi {escape_markdown_v2(user.first_name)}\\! 👋\n\n"
            f"Let's set up your Zo House Builder profile\\. "
            f"This will only take a minute\\.\n\n"
        )

        if not has_github:
            welcome_msg += "Please enter your GitHub username to continue\\:"
            user_setup_state[user_id]["step"] = "github"
            query.edit_message_text(welcome_msg, parse_mode="MarkdownV2")
            return GITHUB_USERNAME
        elif not has_wallet:
            welcome_msg += (
                "Please enter your wallet address to complete your profile\\:"
            )
            user_setup_state[user_id]["step"] = "wallet"
            query.edit_message_text(welcome_msg, parse_mode="MarkdownV2")
            return WALLET_ADDRESS

        return ConversationHandler.END

    elif query.data == "setup_github":
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
            text=contribute_text, reply_markup=reply_markup, parse_mode="MarkdownV2"
        )

    elif query.data == "back_to_menu":
        # Return to main menu
        welcome_message = (
            "Zo House Builder Bot\\! 👋\n\n"
            "What would you like to do?\n\n"
            "Use these commands to navigate:\n"
            "\\- /profile \\- View your builder profile\n"
            "\\- /projects \\- Browse featured projects\n"
            "\\- /help \\- Show all available commands\n\n"
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
            text=welcome_message, reply_markup=reply_markup, parse_mode="MarkdownV2"
        )


def save_github_username(update: Update, context: CallbackContext) -> int:
    """Save GitHub username and proceed to next step."""
    user_id = update.effective_user.id
    github_username = update.message.text.strip()  # Strip whitespace

    # Debugging log
    logger.info(
        f"Attempting to save GitHub username '{github_username}' for user {user_id}"
    )

    # Basic validation
    if not github_username or len(github_username) < 1:
        update.message.reply_text(
            "GitHub username cannot be empty. Please enter a valid GitHub username:"
        )
        return GITHUB_USERNAME

    # Check if username is already set
    user_data = database.get_user(user_id)
    if user_data and user_data.get("github_username"):
        update.message.reply_text(
            "Your GitHub username is already set and cannot be changed."
        )
        # If wallet is also set, end the conversation, otherwise continue to wallet
        if user_data.get("wallet_address"):
            return ConversationHandler.END
        else:
            update.message.reply_text(
                "Please enter your Base wallet address to complete your profile:"
            )
            if user_id in user_setup_state:
                user_setup_state[user_id]["step"] = "wallet"
            return WALLET_ADDRESS

    try:
        # Save the username
        database.update_user_github(user_id, github_username)

        # Update user state - ensure dict exists first
        if user_id not in user_setup_state:
            user_setup_state[user_id] = {}
        user_setup_state[user_id]["step"] = "github_done"

        # Escape github_username for MarkdownV2
        escaped_username = escape_markdown_v2(github_username)

        update.message.reply_text(
            f"Great\\! I've saved '{escaped_username}' as your GitHub username\\.\n\n"
            f"Now, please enter your wallet address to complete your profile\\:",
            parse_mode="MarkdownV2",
        )

        user_setup_state[user_id]["step"] = "wallet"
        logger.info(
            f"Successfully saved GitHub username for user {user_id}, requesting wallet address"
        )
        return WALLET_ADDRESS

    except Exception as e:
        logger.error(f"Error saving GitHub username for user {user_id}: {e}")
        update.message.reply_text(
            "There was an error saving your GitHub username. Please try again later or contact support."
        )
        return ConversationHandler.END


def get_return_to_group_link(group_id):
    """Generate a link to return to the group chat."""
    # Format the group ID properly for Telegram deep linking
    if str(group_id).startswith("-100"):
        # Already in the proper format
        chat_id = str(group_id)[4:]  # Remove the "-100" prefix
    elif str(group_id).startswith("-"):
        # Legacy group format
        chat_id = str(group_id)[1:]  # Remove the "-" prefix
    else:
        chat_id = str(group_id)

    return f"https://t.me/c/{chat_id}"


def save_wallet_address(update: Update, context: CallbackContext) -> int:
    """Save wallet address and complete profile setup."""
    user_id = update.effective_user.id
    wallet_address = update.message.text.strip()  # Strip whitespace

    # Check if wallet is already set
    user_data = database.get_user(user_id)
    if user_data and user_data.get("wallet_address"):
        update.message.reply_text(
            "Your wallet address is already set and cannot be changed."
        )
        return ConversationHandler.END

    # Validate Ethereum address format
    import re
    eth_regex = re.compile(r'^0x[a-fA-F0-9]{40}$')
    if not eth_regex.match(wallet_address):
        update.message.reply_text(
            "Invalid wallet address format. Please enter a valid Base wallet address that starts with '0x' followed by 40 hexadecimal characters:"
        )
        return WALLET_ADDRESS

    # Save the wallet address
    database.update_user_wallet(user_id, wallet_address)

    # Update user state
    user_setup_state[user_id]["step"] = "completed"

    # Format wallet for display
    if len(wallet_address) > 10:
        wallet_display = wallet_address[:6] + "..." + wallet_address[-4:]
    else:
        wallet_display = wallet_address  # Fixed: was using undefined wallet_display variable

    escaped_wallet = escape_markdown_v2(wallet_display)

    # Check if user came from a group
    group_id = (
        group_message_cache[user_id].get("group_id")
        if user_id in group_message_cache
        else None
    )

    if group_id:
        completion_msg = (
            f"🎉 *Profile Complete\\!* 🎉\n\n"
            f"Your wallet has been set to: `{escaped_wallet}`\n\n"
            f"Your Zo House Builder profile is now complete\\! You can now return to the group\\.\n\n"
        )

        try:
            welcome_back_msg = context.bot.send_message(
                chat_id=group_id,
                text=f"🎉 {update.effective_user.first_name} has completed their Zo House Builder profile setup! Welcome back!",
            )

            group_url = (
                f"https://t.me/c/{str(group_id)[1:]}/{welcome_back_msg.message_id}"
            )

            keyboard = [[InlineKeyboardButton("Back to Group", url=group_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            context.bot.send_message(
                user_id,
                text=completion_msg,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            logger.error(f"Error sending group notification: {e}")

        if user_id in group_message_cache:
            try:
                context.bot.delete_message(
                    chat_id=group_message_cache[user_id]["group_id"],
                    message_id=group_message_cache[user_id]["message_id"],
                )
            except Exception as e:
                logger.error(f"Error deleting redirect message: {e}")
            # Remove from cache
            del group_message_cache[user_id]
    else:
        completion_msg = (
            f"🎉 *Profile Complete\\!* 🎉\n\n"
            f"Your wallet has been set to: `{escaped_wallet}`\n\n"
            f"Your Zo House Builder profile is now complete\\! "
            f"You can now get back to the group chat\\!"
        )
        update.message.reply_text(completion_msg, parse_mode="MarkdownV2")

    # Clean up user state
    if user_id in user_setup_state:
        del user_setup_state[user_id]

    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    update.message.reply_text("Operation cancelled\\.", parse_mode="MarkdownV2")

    # Clean up user state
    user_id = update.effective_user.id
    if user_id in user_setup_state:
        del user_setup_state[user_id]

    return ConversationHandler.END


def projects_command(update: Update, context: CallbackContext) -> None:
    """Show featured projects."""
    update.message.reply_text(
        "🚀 *Featured Zo House Projects* 🚀\n\n"
        "Here are some highlighted projects from our community:\n\n"
        "• *Project listings coming soon*\n\n"
        "Want to add your project? Use the /submit command\\!",
        parse_mode="MarkdownV2",
    )


def contribute_command(update: Update, context: CallbackContext) -> None:
    """Show contribution opportunities."""
    # Escape the github_link for the message
    escaped_link = escape_markdown_v2(github_link)

    update.message.reply_text(
        "🔨 *How to Contribute to Zo House* 🔨\n\n"
        "Looking to get involved? Here are some ways:\n\n"
        "1️⃣ Follow our GitHub organization: [Zo House GitHub](" + escaped_link + ")\n"
        "2️⃣ Check open issues and start contributing\n"
        "3️⃣ Share your own projects with the community\n"
        "4️⃣ Nominate and support other builders\n\n"
        "Your contributions will increase your Builder Score\\!",
        parse_mode="MarkdownV2",
    )


def linkgithub_command(update: Update, context: CallbackContext) -> None:
    """Command to initiate GitHub username collection."""
    # Check if GitHub username is already set
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    if user_data and user_data.get("github_username"):
        github_username = user_data.get("github_username")
        escaped_username = escape_markdown_v2(github_username)
        update.message.reply_text(
            f"Your GitHub username is already set to '{escaped_username}' and cannot be changed\\.",
            parse_mode="MarkdownV2",
        )
        return ConversationHandler.END

    update.message.reply_text(
        "Please enter your GitHub username:", parse_mode="MarkdownV2"
    )
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

        escaped_wallet = escape_markdown_v2(str(wallet_display))

        update.message.reply_text(
            f"Your wallet address is already set to '{escaped_wallet}' and cannot be changed\\.",
            parse_mode="MarkdownV2",
        )
        return ConversationHandler.END

    update.message.reply_text(
        "Please enter your wallet address:", parse_mode="MarkdownV2"
    )
    return WALLET_ADDRESS


github_link = "https://github.com/zohouse"


def escape_markdown_v2(text):
    """
    Helper function to escape special characters for MarkdownV2 format.
    Escapes: _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    special_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join([f"\\{c}" if c in special_chars else c for c in text])


def test_command(update: Update, context: CallbackContext) -> None:
    """Send a test message with MarkdownV2 formatting."""
    # Escape the github_link for MarkdownV2
    escaped_github_link = escape_markdown_v2(github_link)

    test_message = (
        "*bold \\*text*\n"
        "_italic \\*text_\n"
        "__underline__\n"
        "~strikethrough~\n"
        "||spoiler||\n"
        "*bold _italic bold ~italic bold strikethrough ||italic bold strikethrough spoiler||~ __underline italic bold___ bold*\n\n"
        f"[Zo House GitHub]({escaped_github_link})\n"
        "[inline URL](http://www\\.example\\.com/)\n"
        "[inline mention of a user](tg://user?id=123456789)\n"
        "![👍](tg://emoji?id=5368324170671202286)\n"
        "`inline fixed\\-width code`\n"
        "```\n"
        "pre\\-formatted fixed\\-width code block\n"
        "```\n"
        "```python\n"
        "# This is Python code\n"
        "def hello_world():\n"
        '    print("Hello, Zo House!")\n'
        "```\n\n"
        ">Block quotation started\n"
        ">Block quotation continued\n"
        ">Block quotation continued\n"
        ">Block quotation continued\n"
        ">The last line of the block quotation\n\n"
        "**>The expandable block quotation started right after the previous block quotation\n"
        ">It is separated from the previous block quotation by an empty bold entity\n"
        ">Expandable block quotation continued\n"
        ">Hidden by default part of the expandable block quotation started\n"
        ">Expandable block quotation continued\n"
        ">The last line of the expandable block quotation with the expandability mark||"
    )

    update.message.reply_text(test_message, parse_mode="MarkdownV2")


def send_github_engagement_reminder(context: CallbackContext):
    """Send periodic reminders to engage with GitHub"""
    try:
        users = database.get_all_users()
        for user in users:
            try:
                if not user.get(
                    "github_star_check", False
                ):  # Using this as placeholder
                    # Escape user's first_name for MarkdownV2
                    escaped_name = escape_markdown_v2(user["first_name"])

                    reminder_text = (
                        f"Hey {escaped_name}\\! 👋\n\n"
                        f"Have you checked out the Zo House GitHub repository lately?\n\n"
                        f"Starring our repo helps you:\n"
                        f"• Stay updated with new projects\n"
                        f"• Track your contributions\n"
                        f"• Support the community's growth\n\n"
                        f"Take a second\\! 🚀"
                    )

                    keyboard = [[InlineKeyboardButton("⭐️ Star Now", url=github_link)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    context.bot.send_message(
                        chat_id=user["user_id"],
                        text=reminder_text,
                        reply_markup=reply_markup,
                        parse_mode="MarkdownV2",
                    )
            except Exception as e:
                print(f"Error sending reminder to user {user['user_id']}: {e}")
    except Exception as e:
        print(f"Error in GitHub engagement reminder: {e}")


def handle_group_message(update: Update, context: CallbackContext) -> None:
    """Process group messages to track user activity."""
    # Debug logging
    logger.info(
        f"Received message in chat {update.effective_chat.id}, group ID env var: {TELEGRAM_GROUP_ID}"
    )

    # Only process messages from the configured group
    if not TELEGRAM_GROUP_ID:
        logger.warning("TELEGRAM_GROUP_ID not set in environment variables")
        return

    # Check if ID matches and log the result
    if str(update.effective_chat.id) != str(TELEGRAM_GROUP_ID):
        logger.info(
            f"Message not from target group. Got {update.effective_chat.id}, expected {TELEGRAM_GROUP_ID}"
        )
        return

    logger.info("Message is from target group - processing")

    # Get basic message info
    user = update.effective_user
    if not user:
        logger.warning("No user found in the message")
        return

    user_id = user.id
    message = update.effective_message
    logger.info(f"Processing message from user {user_id}: {user.first_name}")

    # Skip messages with commands
    if message.text and message.text.startswith("/"):
        logger.info("Skipping command message")
        return

    # Get or create user in database
    try:
        database.get_or_create_user(user_id, user.username, user.first_name)
        logger.info(f"User {user_id} retrieved or created in database")
    except Exception as e:
        logger.error(f"Error getting/creating user: {e}")
        return

    # Update message count
    try:
        result = database.update_telegram_activity(user_id, "messages")
        users_data = database.get_all_users()
        if users_data:
            response = compute_builder_scores(users_data)
            for r in response:
                database.update_user_builder_score(
                    r.get("user_id"), r.get("builder_score")
                )
        logger.info(f"Updated message count for user {user_id}, result: {result}")
    except Exception as e:
        logger.error(f"Error updating telegram activity: {e}")

    # If it's a reply to another message, count it as a reply
    if message.reply_to_message:
        try:
            database.update_telegram_activity(user_id, "replies")
            users_data = database.get_all_users()
            if users_data:
                response = compute_builder_scores(users_data)
                for r in response:
                    database.update_user_builder_score(
                        r.get("user_id"), r.get("builder_score")
                    )

            logger.info(f"Updated reply count for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating reply count: {e}")


def leaderboard_command(update: Update, context: CallbackContext) -> None:
    """Show the top builders by builder score."""
    try:
        # Get all users from the database
        users = database.get_all_users()

        users_with_scores = [
            user
            for user in users
            if user.get("builder_score") is not None
            and float(user.get("builder_score", 0)) > 0
        ]

        # Debug log the users data
        logger.info(f"Retrieved users data: {users_with_scores}")

        # Check if users is None or empty
        if not users_with_scores:
            update.message.reply_text(
                "No builders found yet\\! Be the first to contribute\\!",
                parse_mode="MarkdownV2",
            )
            return

        # Sort users by builder score in descending order
        # Make sure to handle None values and convert to float for sorting
        sorted_users = sorted(
            users_with_scores,
            key=lambda x: float(x.get("builder_score", 0)),
            reverse=True,
        )

        # Take top 10 users
        top_users = sorted_users[:10]

        if not top_users:
            update.message.reply_text(
                "No builders found yet\\! Be the first to contribute\\!",
                parse_mode="MarkdownV2",
            )
            return

        # Format the leaderboard message
        leaderboard_text = "🏆 *Zo House Builder Leaderboard* 🏆\n\n"

        for i, user in enumerate(top_users):
            # Get user details
            position = i + 1
            name = user.get("first_name", "Unknown")
            username = user.get("username", "no_username")

            # Handle different types of builder_score (float, int, None)
            score = user.get("builder_score", 0)
            if score is None:
                score = 0

            # Format score to 2 decimal places if it's a float
            if isinstance(score, float):
                score_str = f"{score:.2f}"
            else:
                score_str = str(score)

            github = user.get("github_username", "Not linked")
            if github is None:
                github = "Not linked"

            # Format medal emojis for top 3
            medal = (
                "🥇"
                if position == 1
                else "🥈"
                if position == 2
                else "🥉"
                if position == 3
                else f"{position}\\."
            )

            # Escape special characters for MarkdownV2
            escaped_name = escape_markdown_v2(str(name))
            escaped_username = escape_markdown_v2(
                str(username) if username else "no\\_username"
            )
            escaped_github = escape_markdown_v2(str(github))
            escaped_score = escape_markdown_v2(score_str)

            # Add user to leaderboard text
            leaderboard_text += f"{medal} *{escaped_name}*"
            if username:
                leaderboard_text += f" \\(@{escaped_username}\\)"
            leaderboard_text += "\n"
            leaderboard_text += f"   ├ Score: {escaped_score} points\n"
            leaderboard_text += f"   └ GitHub: {escaped_github}\n\n"

        # Add motivational footer
        leaderboard_text += "_Contribute more to rise in the ranks\\!_ 🚀"

        # Send the leaderboard message
        update.message.reply_text(leaderboard_text, parse_mode="MarkdownV2")

    except Exception as e:
        logger.error(f"Error displaying leaderboard: {e}", exc_info=True)
        update.message.reply_text(
            "Sorry, there was an error generating the leaderboard\\. Please try again later\\.",
            parse_mode="MarkdownV2",
        )


def score_command(update: Update, context: CallbackContext) -> None:
    """Show the user's builder score."""
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    if not user_data:
        # User doesn't have a profile - prompt them to create one
        if not is_private_chat(update):
            # In group chat - redirect to DM
            group_msg = (
                f"Hi {update.effective_user.first_name}! "
                f"Please set up your profile in our private chat first to view your score."
            )
            update.message.reply_text(group_msg)

            # Send DM to user
            context.bot.send_message(
                user_id,
                f"Hi {update.effective_user.first_name}! Let's set up your Zo House Builder profile. "
                f"Type /start to begin.",
            )
        else:
            # In private chat - start setup
            update.message.reply_text(
                "You need to set up your profile first to track your score\\. Let's do that now\\!",
                parse_mode="MarkdownV2",
            )
            return start_private_setup_flow(update, context)
        return

    # Get the score, default to 0 if not set
    builder_score = user_data.get("builder_score", 0)

    # Format score to 2 decimal places if it's a float
    if isinstance(builder_score, float):
        score_str = f"{builder_score:.2f}"
    else:
        score_str = str(builder_score)

    # Escape for MarkdownV2
    escaped_score = escape_markdown_v2(score_str)

    # Build motivational text based on score
    if float(builder_score) == 0:
        motivation = "Start contributing to earn your first points\\!"
    elif float(builder_score) < 10:
        motivation = "Great start\\! Keep engaging with the community\\."
    elif float(builder_score) < 50:
        motivation = (
            "You're making good progress\\! Check out more ways to contribute\\."
        )
    else:
        motivation = "Impressive score\\! You're a valuable builder in our community\\."

    score_text = (
        f"🏆 *Your Builder Score* 🏆\n\n"
        f"Current Score: *{escaped_score} points*\n\n"
        f"{motivation}\n\n"
        f"*How to increase your score:*\n"
        f"• Engage in group discussions\n"
        f"• Contribute to GitHub projects\n"
        f"• Help other community members\n"
        f"Use /leaderboard to see the top builders\\!"
    )

    update.message.reply_text(score_text, parse_mode="MarkdownV2")


def nominate_command(update: Update, context: CallbackContext) -> None:
    """Nominate a fellow builder to give them recognition."""
    user_id = update.effective_user.id
    user_data = database.get_user(user_id)

    # Check if user has a profile
    if not user_data:
        update.message.reply_text(
            "You need to set up your profile first before nominating others\\. Use /start to set up your profile\\.",
            parse_mode="MarkdownV2",
        )
        return

    # Check if command has arguments (username to nominate)
    if not context.args:
        update.message.reply_text(
            "Please specify the username of the builder you want to nominate\\.\n"
            "Example: `/nominate username`",
            parse_mode="MarkdownV2",
        )
        return

    # Get the username to nominate (remove @ if present)
    nominee_username = context.args[0].lstrip("@")

    # Process the nomination
    result = database.add_nomination(user_id, nominee_username)

    if result["status"] == "success":
        # Format the nominee's data for display
        nominee = result["nominee"]
        current_nominations = nominee.get("nominations_received", 0)

        # Recalculate builder scores
        users_data = database.get_all_users()
        if users_data:
            response = compute_builder_scores(users_data)
            for r in response:
                database.update_user_builder_score(
                    r.get("user_id"), r.get("builder_score")
                )

        # Send a nice confirmation message
        escaped_username = escape_markdown_v2(nominee_username)
        escaped_name = escape_markdown_v2(nominee.get("first_name", nominee_username))

        success_message = (
            f"🎖 *Nomination Successful\\!* 🎖\n\n"
            f"You have nominated @{escaped_username} as a valuable Zo House builder\\!\n\n"
            f"{escaped_name} has now received *{current_nominations}* nomination\\(s\\)\\.\n\n"
            f"Thank you for recognizing great contributors to our community\\!"
        )

        update.message.reply_text(success_message, parse_mode="MarkdownV2")

        # Notify the nominated user (if we can)
        try:
            nominee_id = nominee.get("user_id")
            if nominee_id:
                nominator_name = escape_markdown_v2(update.effective_user.first_name)
                notification = (
                    f"🌟 *You've been nominated\\!* 🌟\n\n"
                    f"{nominator_name} has recognized you as a valuable Zo House builder\\!\n\n"
                    f"You now have *{current_nominations}* nomination\\(s\\) in total\\.\n\n"
                    f"Keep up the great work\\!"
                )
                context.bot.send_message(
                    chat_id=nominee_id, text=notification, parse_mode="MarkdownV2"
                )
        except Exception as e:
            logger.error(f"Error sending nomination notification: {e}")
    else:
        # Send error message
        update.message.reply_text(f"⚠️ {result['message']}", parse_mode="None")


def main() -> None:
    # Start both the telegram bot and the handler server in separate threads

    """Start the bot."""
    # Create the Updater and pass it your bot's token
    updater = Updater(TELEGRAM_TOKEN)
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    print(f"Starting bot with TELEGRAM_GROUP_ID: {TELEGRAM_GROUP_ID}")

    # Basic command handlers
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("projects", projects_command))
    dispatcher.add_handler(CommandHandler("contribute", contribute_command))
    dispatcher.add_handler(CommandHandler("test", test_command))
    dispatcher.add_handler(CommandHandler("leaderboard", leaderboard_command))
    dispatcher.add_handler(CommandHandler("score", score_command))
    dispatcher.add_handler(
        CommandHandler("nominate", nominate_command)
    )  # Add nominate command handler

    # This is the main conversation handler for profile setup
    profile_setup_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("profile", profile_command),
            CallbackQueryHandler(
                button_callback, pattern="^(setup_github|link_wallet|start_setup)$"
            ),
        ],
        states={
            GITHUB_USERNAME: [
                MessageHandler(Filters.text & ~Filters.command, save_github_username)
            ],
            WALLET_ADDRESS: [
                MessageHandler(Filters.text & ~Filters.command, save_wallet_address)
            ],
            RETURNING_TO_GROUP: [
                CallbackQueryHandler(button_callback, pattern="^return_to_group")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="profile_setup",
        persistent=False,
    )

    # Register the conversation handler (this should be first to prioritize it)
    dispatcher.add_handler(profile_setup_handler)

    # Handle other callback queries that aren't part of the conversation
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    # Add start handler - but make sure it's added AFTER the conversation handler
    # that includes 'start' as an entry point to avoid conflicts
    dispatcher.add_handler(CommandHandler("start", start))

    dispatcher.add_handler(
        MessageHandler(
            Filters.chat_type.groups & ~Filters.command, handle_group_message
        ),
        group=10,
    )
    # Start the Bot
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
