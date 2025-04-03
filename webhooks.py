from fastapi import FastAPI, Request, HTTPException, status
import hmac
import hashlib
import requests
import os
import uvicorn

app = FastAPI()

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
GITHUB_WEBHOOK_SECRET = "J/65d0qFORIlkP7uY8aB/JKYwA4="


def verify_github_signature(signature: str, body: bytes) -> bool:
    """Verify GitHub webhook signature"""
    if not GITHUB_WEBHOOK_SECRET:
        raise ValueError("GitHub webhook secret not configured")

    expected_signature = (
        "sha256="
        + hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(signature, expected_signature)


def send_to_telegram_group(text: str) -> bool:
    """Send message to Telegram group"""
    if not TELEGRAM_TOKEN or not TELEGRAM_GROUP_ID:
        raise ValueError("Telegram credentials not configured")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_GROUP_ID,
        "parse_mode": "Markdown",
        "text": text,
        "disable_web_page_preview": True,  # Fixed typo (was 'disable_webpage_preview')
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")
        return False


def handle_push_event(payload: dict) -> str:
    """Handle GitHub push events"""
    print("This is payload", payload)
    repo = payload["repository"]["full_name"]
    branch = payload["ref"].split("/")[-1]
    commit_count = len(payload["commits"])
    pusher = payload["pusher"]["name"]
    compare_url = payload["compare"]

    message = (
        f"📌 *New Push to {repo} ({branch})*\n"
        f"👤 By: {pusher}\n"
        f"🔢 Commits: {commit_count}\n"
        f"🔗 [View Changes]({compare_url})"
    )
    return message


def handle_pull_request(payload: dict) -> str:
    """Handle GitHub PR events"""
    print("This is payload", payload)
    action = payload["action"]
    pr = payload["pull_request"]  
    repo = pr["base"]["repo"]["full_name"]
    title = pr["title"]
    user = pr["user"]["login"]
    url = pr["html_url"]

    message = (
        f"🔄 *PR {action.capitalize()} in {repo}*\n"
        f"📢 Title: {title}\n"
        f"👤 By: {user}\n"
        f"🔗 [View PR]({url})"
    )
    return message


def handle_issues_event(payload: dict) -> str:
    """Handle GitHub issue events"""
    print("This is payload", payload)
    action = payload["action"]
    issue = payload["issue"]
    repo = payload["repository"]["full_name"]  # Fixed path
    title = issue["title"]
    user = issue["user"]["login"]
    url = issue["html_url"]

    message = (
        f"⚠️ *Issue {action.capitalize()} in {repo}*\n"
        f"📢 Title: {title}\n"
        f"👤 By: {user}\n"
        f"🔗 [View Issue]({url})"
    )

    print("This is message", message)
    return message


@app.post("/github_webhook")
async def github_webhook(request: Request):
    """Handle GitHub webhook events"""
    try:
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")

        if not signature or not verify_github_signature(signature, body):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing signature",
            )

        payload = await request.json()
        print("This is payload", payload)
        event = request.headers.get("X-GitHub-Event")
        print("This is event", event)

        if event == "push":
            message = handle_push_event(payload)
        elif event == "pull_request":
            message = handle_pull_request(payload)
        elif event == "issues":
            message = handle_issues_event(payload)
        else:
            return {"status": "ignored", "event": event}

        if not send_to_telegram_group(message):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send Telegram message",
            )

        return {"status": "success", "event": event}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)
