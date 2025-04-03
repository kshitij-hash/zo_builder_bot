# Zo House Builder Bot

A Telegram bot that acts as the official community agent for Zo House — a network of hacker houses and builder spaces. This bot helps surface new projects, track contributor activity, and reward participation in the Zo House builder community.

## Features

### Telegram Bot Core Features
- Pull and display relevant projects from DoraHacks tagged with Zo House themes
- Enable users to:
  - Share personal project milestones
  - Nominate fellow builders for shoutouts
  - View project links, Builder Scores, and contributor profiles

### GitHub Integration
- Integrate with the Zo House GitHub repository:
  - Announce new commits, pull requests, and issues in Telegram
  - Attribute GitHub activity to contributors (via GitHub username)
  - Include GitHub contributions in Builder Score logic
  - `/contribute` command that shows open GitHub issues and contribution tips

### Builder Score System
- Assign each member a Builder Score based on:
  - Project submissions (DoraHacks or manual)
  - GitHub activity (commits, PRs, issues)
  - Nominations and engagement within Telegram
- Allow users to check scores via `/score` or `/profile`

### Leaderboard & Wallets
- Show top builders in a `/leaderboard` command
- Update leaderboard weekly or monthly with chat highlights
- Let users link their wallets via `/linkwallet`
- Display wallet + score in public profile

### Admin & Automation Features
- Automatic onboarding for new members
- Weekly recap posts highlighting community achievements
- Admin tools for moderation and special announcements

## Technology Stack
- Telegram Bot API
- Bot Framework: python-telegram-bot
- GitHub API for repository integration
- Database: MongoDB
- Hosting: [AWS Lambda/DigitalOcean/Heroku]

## Setup & Installation

### Prerequisites
- Python 3.8+
- Telegram Bot token (from BotFather)
- GitHub API credentials
- MongoDB database

### Installation Steps
1. Clone the repository
```bash
git clone https://github.com/your-org/builder-bot.git
cd builder-bot
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the bot
```bash
python bot.py
```

## Development Roadmap

### Phase 1: Foundation Setup
- Bot architecture and core commands
- GitHub integration
- DoraHacks integration

### Phase 2: Core Features
- Builder Score system
- User management and profiles
- Leaderboard and engagement features

### Phase 3: Testing & Deployment
- Comprehensive testing
- Production deployment
- Community feedback and iterations

## Current Implementation Status

The initial implementation includes:
- Basic bot setup with core commands
- User registration and profile management
- GitHub username and wallet linking
- MongoDB database integration for user data storage
- Placeholder implementations for projects and contributions

Next steps:
- GitHub API integration for tracking repository activities
- DoraHacks integration for project discovery
- Implement the Builder Score calculation logic
- Add leaderboard functionality