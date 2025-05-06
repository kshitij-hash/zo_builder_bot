# Zo House Builder Bot

A Telegram bot that acts as the official community agent for Zo House — a network of hacker houses and builder spaces. This bot helps surface new projects, track contributor activity, and reward participation in the Zo House builder community.

## Features

### Telegram Bot Core Features
- Enable users to:
  - Nominate fellow builders for shoutouts
  - View project links, Builder Scores, and contributor profiles
- Day-to-day commands:
  - `/start` - Setup their builder profile
  - `/help` - List all available commands
  - `/profile` - View your profile information and Builder Score
  - `/nominate @username` - Nominate a fellow builder for recognition
  - `/score` - Check your Builder Score
  - `/leaderboard` - View the top builders in the community

### GitHub Integration
- Integrate with the Zo House GitHub repository:
  - Announce new commits, pull requests, and issues in Telegram
  - Attribute GitHub activity to contributors (via GitHub username)
  - Include GitHub contributions in Builder Score logic

### Builder Score System
- Assign each member a Builder Score based on:
  - GitHub activity (commits, PRs, issues)
  - Nominations and engagement within Telegram
- Allow users to check scores via `/score` or `/profile`

### Leaderboard & Wallets
- Show top builders in a `/leaderboard` command
- Display wallet + score in public profile

### Automation Features
- Automatic onboarding for new members
- Weekly recap posts highlighting community achievements

## Technology Stack
- Telegram Bot API
- Bot Framework: python-telegram-bot
- GitHub webhooks for real-time updates
- Database: MongoDB

## Setup & Installation

### Prerequisites
- Python 3.8+
- Telegram Bot token (from BotFather)
- GitHub webhook secret
- MongoDB database
- Public URL endpoint for webhook (for GitHub integration)

### Environment Variables
Create a `.env` file with the following variables:
- `TELEGRAM_TOKEN`: Your Telegram bot token from BotFather
- `TELEGRAM_GROUP_ID`: ID of the Telegram group where the bot will operate
- `GITHUB_WEBHOOK_SECRET`: Secret for verifying GitHub webhooks
- `MONGODB_URI`: Connection string for MongoDB
- `MONGODB_DB`: MongoDB database name

### Installation Steps
1. Clone the repository
```bash
git clone https://github.com/your-org/zo-builder-bot.git
cd zo-builder-bot
```

2. Install dependencies
```bash
python3 -m venv .venv #or python -m venv .venv
pip install -r requirements.txt
```

3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your configuration values
```

4. Run the main bot
```bash
python bot.py
```

5. Run the webhook server (in a separate terminal or process)
```bash
uvicorn webhooks:app --reload
```

### Setting Up GitHub Webhooks
1. Go to your GitHub organization settings
2. Navigate to "Webhooks" and click "Add webhook"
3. Set the Payload URL to your `WEBHOOK_URL` value
4. Set Content type to "application/json"
5. Enter your `GITHUB_WEBHOOK_SECRET` value
6. Select events to trigger the webhook:
   - Pull requests
   - Issues
   - Issue comments
   - Push events
7. Ensure the webhook is active and click "Add webhook"