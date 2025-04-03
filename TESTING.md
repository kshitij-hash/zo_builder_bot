# Testing Guide for Zo House Builder Bot

This guide will help you test the current implementation of the Zo House Builder Bot.

## Prerequisites Setup

### 1. Create a Telegram Bot for Testing

1. Open Telegram and search for `@BotFather`
2. Start a conversation and send `/newbot`
3. Follow the instructions to create a new bot
4. Copy the API token provided by BotFather

### 2. Set Up MongoDB

#### Option A: Local MongoDB
1. Install MongoDB on your local machine
2. Start the MongoDB service:
   ```
   sudo systemctl start mongod
   ```
3. Verify it's running:
   ```
   sudo systemctl status mongod
   ```

#### Option B: MongoDB Atlas (Cloud)
1. Create a free account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a new cluster
3. Set up database access (username/password)
4. Set up network access (allow your IP or 0.0.0.0/0 for testing)
5. Get your connection string

### 3. Configure Environment Variables

1. Create a `.env` file in the project root:
   ```
   cp .env.example .env
   ```
2. Edit the `.env` file with your actual credentials:
   ```
   TELEGRAM_TOKEN=your_telegram_bot_token_from_botfather
   BOT_USERNAME=your_bot_username
   GITHUB_TOKEN=your_github_token  # Optional for initial testing
   MONGODB_URI=your_mongodb_connection_string
   MONGODB_DB=zo_house_bot_test
   ADMIN_IDS=your_telegram_user_id  # Optional for initial testing
   ```

## Running the Bot

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the bot:
   ```
   python bot.py
   ```

3. You should see logging information in the console indicating the bot has started.

## Testing Bot Functionality

### Basic Commands

1. Open Telegram and search for your bot's username
2. Start a conversation with `/start`
   - Verify you receive a welcome message with buttons
   - Check that your user is created in the database

3. Test the `/help` command
   - Verify you receive a help message with available commands

4. Test the `/profile` command
   - Verify you see your profile (initially with no GitHub or wallet)

5. Test the `/projects` command
   - Verify you see the projects placeholder message

6. Test the `/contribute` command
   - Verify you see contribution information

### Conversation Flows

1. Test GitHub linking
   - Click "Setup GitHub" button from `/start` or `/profile`
   - Enter a GitHub username (e.g., "testuser")
   - Verify confirmation message
   - Check `/profile` to see your GitHub username is linked

2. Test wallet linking
   - Click "Link Wallet" button from `/start` or `/profile`
   - Enter a wallet address (e.g., "0x123456789abcdef...")
   - Verify confirmation message
   - Check `/profile` to see your wallet is linked

### Verifying Database Operations

1. Connect to your MongoDB instance:
   ```
   # For local MongoDB
   mongosh
   
   # For MongoDB Atlas
   mongosh "your_connection_string"
   ```

2. Check the database collections:
   ```
   use zo_house_bot_test
   db.users.find()
   ```

3. Verify your user document exists with:
   - Your Telegram user_id
   - The GitHub username you entered
   - The wallet address you entered
   - A builder_score of 0

## Troubleshooting

### Bot Not Responding
- Check that your bot is running (terminal output)
- Verify your TELEGRAM_TOKEN is correct
- Try stopping and restarting the bot

### Database Connection Issues
- Verify your MongoDB is running
- Check your connection string in the .env file
- Make sure network access is configured correctly

### Conversation Handlers Not Working
- Make sure you're clicking the buttons directly from bot messages
- Check the terminal for any errors in the conversation flow
- Try restarting the conversation with /start
