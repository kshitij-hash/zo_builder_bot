import hashlib
import hmac
import os

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status

from database import (
    update_github_contribution,
    get_all_users,
    update_user_builder_score,
)
from builder_score import compute_builder_scores

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "fallback_token")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "fallback_group_id")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "fallback_secret")


def verify_github_signature(signature: str, body: bytes) -> bool:
    if not GITHUB_WEBHOOK_SECRET:
        raise ValueError("GitHub webhook secret not configured")

    expected_signature = (
        "sha256="
        + hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(signature, expected_signature)


def send_to_telegram_group(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_GROUP_ID:
        raise ValueError("Telegram credentials not configured")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_GROUP_ID,
        "parse_mode": "MarkdownV2",
        "text": text,
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Telegram message: {e}")
        return False


def escape_md_v2(text):
    if not text:
        return ""
    chars_to_escape = "_*[]()~`>#+-=|.!{}"
    for char in chars_to_escape:
        text = text.replace(char, f"\\{char}")
    return text


def handle_push_event(payload: dict) -> str:
    try:
        repo = payload["repository"]["name"]
        repo_url = payload["repository"]["html_url"]
        branch = payload["ref"].split("/")[-1]
        commit_count = len(payload["commits"])
        pusher = payload["pusher"]["name"]
        pusher_url = f"https://github.com/{pusher}"
        compare_url = payload["compare"]

        is_new_branch = payload.get("created", False)
        is_deleted_branch = payload.get("deleted", False)

        # Escape values
        branch_name = escape_md_v2(branch)
        repo_name = escape_md_v2(repo)
        pusher_name = escape_md_v2(pusher)
        repo_url_escaped = escape_md_v2(repo_url)
        pusher_url_escaped = escape_md_v2(pusher_url)
        compare_url_escaped = escape_md_v2(compare_url)

        if is_deleted_branch:
            return (
                f"🗑️ *Branch Deleted*\n\n"
                f"[{pusher_name}]({pusher_url_escaped}) just deleted branch `{branch_name}` "
                f"from [{repo_name}]({repo_url_escaped})"
            )

        if is_new_branch:
            message = (
                f"🌱 *New Branch Alert\\!*\n\n"
                f"[{pusher_name}]({pusher_url_escaped}) created branch `{branch_name}` "
                f"in [{repo_name}]({repo_url_escaped})"
            )
            return message
        
        # For regular pushes, make it more conversational
        message = (
            f"💫 *Fresh Code Alert\\!*\n\n"
            f"[{pusher_name}]({pusher_url_escaped}) just pushed "
            f"{commit_count} {('commit' if commit_count == 1 else 'commits')} "
            f"to `{branch_name}` in [{repo_name}]({repo_url_escaped})"
        )

        # Only show latest commit for bigger pushes
        if commit_count == 1:
            commit = payload["commits"][0]
            commit_msg = commit["message"].split("\n")[0]
            if len(commit_msg) > 70:
                commit_msg = commit_msg[:67] + "..."
            message += f"\n\n💬 \"{escape_md_v2(commit_msg)}\""
        elif commit_count > 1 and commit_count <= 3:
            message += "\n\n*Latest commits:*"
            for i in range(min(commit_count, 3)):
                commit = payload["commits"][i]
                commit_msg = commit["message"].split("\n")[0]
                if len(commit_msg) > 50:
                    commit_msg = commit_msg[:47] + "..."
                message += f"\n• {escape_md_v2(commit_msg)}"
        
        # Add a call to action
        message += f"\n\n[🔍 See what's changed]({compare_url_escaped})"

        return message
    except Exception as e:
        print(f"Error formatting push message: {str(e)}")
        return f"New code pushed to {escape_md_v2(payload.get('repository', {}).get('full_name', 'unknown'))}"


def handle_pull_request(payload: dict) -> str:
    try:
        action = payload["action"]
        pr = payload["pull_request"]

        # Basic PR information
        repo = pr["base"]["repo"]["name"]
        repo_url = pr["base"]["repo"]["html_url"]
        title = pr["title"]
        user = pr["user"]["login"]
        user_url = pr["user"]["html_url"]
        pr_url = pr["html_url"]

        # Branch information
        base_branch = pr["base"]["ref"]

        # State information
        is_merged = pr.get("merged", False)
        is_draft = pr.get("draft", False)

        # Escape values
        title_escaped = escape_md_v2(title)
        repo_escaped = escape_md_v2(repo)
        repo_url_escaped = escape_md_v2(repo_url)
        user_escaped = escape_md_v2(user)
        user_url_escaped = escape_md_v2(user_url)
        pr_url_escaped = escape_md_v2(pr_url)

        # Fun emojis for PR actions
        action_emojis = {
            "opened": "🚀",
            "closed": "🔒",
            "merged": "🎉"
        }

        if action == "opened":
            draft_text = " \\(Draft\\)" if is_draft else ""
            
            # Create labels string if labels exist
            labels_text = ""
            if pr.get("labels") and len(pr["labels"]) > 0:
                label_names = [f"`{escape_md_v2(label['name'])}`" for label in pr["labels"][:2]]
                if len(pr["labels"]) > 2:
                    label_names.append("\\+more")
                labels_text = f" • {', '.join(label_names)}"

            # Construct a shorter, more engaging message
            message = (
                f"{action_emojis['opened']} *New PR Alert{draft_text}\\!*\n\n"
                f"*{title_escaped}*\n"
                f"👤 [{user_escaped}]({user_url_escaped}) wants to merge changes into [{repo_escaped}]({repo_url_escaped})\n"
                f"{labels_text}\n\n"
                f"[Check it out \\→]({pr_url_escaped})"
            )

        elif action == "closed":
            if is_merged:
                # More celebratory message for merged PRs
                message = (
                    f"{action_emojis['merged']} *PR Merged Successfully\\!*\n\n"
                    f"*{title_escaped}* just landed in `{escape_md_v2(base_branch)}`\\!\n"
                    f"👏 Kudos to [{user_escaped}]({user_url_escaped}) for the contribution\\!\n\n"
                    f"[See the merged PR \\→]({pr_url_escaped})"
                )
            else:
                # Lighter tone for closed PRs
                message = (
                    f"{action_emojis['closed']} *PR Closed*\n\n"
                    f"*{title_escaped}*\n"
                    f"This PR from [{user_escaped}]({user_url_escaped}) to [{repo_escaped}]({repo_url_escaped}) was closed without merging\\.\n\n"
                    f"[See details \\→]({pr_url_escaped})"
                )
        return message
    except Exception as e:
        print(f"Error formatting PR message: {str(e)}")
        return None


def handle_issues_event(payload: dict) -> str:
    try:
        action = payload["action"]
        issue = payload["issue"]
        repo = payload["repository"]["name"]
        repo_url = payload["repository"]["html_url"]
        title = issue["title"]
        user = issue["user"]["login"]
        user_url = issue["user"]["html_url"]
        issue_url = issue["html_url"]
        issue_number = issue["number"]

        # Escape values
        title_escaped = escape_md_v2(title)
        repo_escaped = escape_md_v2(repo)
        repo_url_escaped = escape_md_v2(repo_url)
        user_escaped = escape_md_v2(user)
        user_url_escaped = escape_md_v2(user_url)
        issue_url_escaped = escape_md_v2(issue_url)

        if action == "opened":
            # Get labels (limit to 3 for brevity)
            labels_text = ""
            if issue["labels"]:
                label_names = [f"`{escape_md_v2(label['name'])}`" for label in issue["labels"][:3]]
                if len(issue["labels"]) > 3:
                    label_names.append("\\+more")
                labels_text = f" • {', '.join(label_names)}"
            
            message = (
                f"🐛 *New Issue Spotted\\!*\n\n"
                f"*{title_escaped}*\n"
                f"👤 [{user_escaped}]({user_url_escaped}) opened an issue in "
                f"[{repo_escaped}]({repo_url_escaped}) \\#{issue_number}"
                f"{labels_text}\n\n"
                f"[🔍 Take a look]({issue_url_escaped})"
            )
        elif action == "closed":
            message = (
                f"✅ *Issue Resolved\\!*\n\n"
                f"Issue *{title_escaped}* has been closed by "
                f"[{user_escaped}]({user_url_escaped}) in "
                f"[{repo_escaped}]({repo_url_escaped})\n\n"
                f"[See details]({issue_url_escaped})"
            )

        return message
    except Exception as e:
        print(f"Error formatting issue message: {str(e)}")
        return None


@app.post("/github_webhook")
async def github_webhook(request: Request):
    try:
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")

        if not signature or not verify_github_signature(signature, body):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing signature",
            )

        payload = await request.json()
        event = request.headers.get("X-GitHub-Event")

        if event == "push":
            message = handle_push_event(payload)

            if "commits" in payload and len(payload["commits"]) > 0:
                for commit in payload["commits"]:
                    if "author" in commit and "username" in commit["author"]:
                        github_username = commit["author"]["username"]
                        update_github_contribution(github_username, "commits")

            users_data = get_all_users()
            if users_data:
                response = compute_builder_scores(users_data)
                for r in response:
                    update_user_builder_score(r.get("user_id"), r.get("builder_score"))

        elif event == "pull_request":
            message = handle_pull_request(payload)

            if payload.get("action") == "opened":
                github_username = payload["pull_request"]["user"]["login"]
                update_github_contribution(github_username, "prs")

            users_data = get_all_users()
            if users_data:
                response = compute_builder_scores(users_data)
                for r in response:
                    update_user_builder_score(r.get("user_id"), r.get("builder_score"))
        elif event == "issues":
            message = handle_issues_event(payload)

            if payload.get("action") == "opened":
                github_username = payload["issue"]["user"]["login"]
                update_github_contribution(github_username, "issues")

            users_data = get_all_users()
            if users_data:
                response = compute_builder_scores(users_data)
                for r in response:
                    update_user_builder_score(r.get("user_id"), r.get("builder_score"))
        else:
            return {"status": "ignored", "event": event}

        if message is not None:
            if not send_to_telegram_group(message):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send Telegram message",
                )
            return {"status": "success", "event": event}
        else:
            return {"status": "ignored", "event": event}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)
