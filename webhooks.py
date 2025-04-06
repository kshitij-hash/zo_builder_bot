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
        pusher_url = f"https://github.com/{pusher}"  # Construct pusher URL
        compare_url = payload["compare"]

        is_new_branch = payload.get("created", False)
        is_deleted_branch = payload.get("deleted", False)

        branch_name = escape_md_v2(branch)
        repo_name = escape_md_v2(repo)
        pusher_name = escape_md_v2(pusher)
        repo_url_escaped = escape_md_v2(repo_url)
        pusher_url_escaped = escape_md_v2(pusher_url)
        compare_url_escaped = escape_md_v2(compare_url)

        if is_deleted_branch:
            return (
                f"🗑️ *Branch Deleted*\n"
                f"📂 Repository: [{repo_name}]({repo_url_escaped})\n"
                f"🌿 Branch: *{branch_name}*\n"
                f"👤 By: [{pusher_name}]({pusher_url_escaped})"
            )

        if is_new_branch:
            message = (
                f"🌱 *New Branch Created*\n"
                f"📂 Repository: [{repo_name}]({repo_url_escaped})\n"
                f"🌿 Branch: *{branch_name}*\n"
                f"👤 By: [{pusher_name}]({pusher_url_escaped})\n"
            )
        else:
            message = (
                f"📌 *New Push to [{repo_name}]({repo_url_escaped})*\n"
                f"🌿 Branch: *{branch_name}*\n"
                f"👤 By: [{pusher_name}]({pusher_url_escaped})\n"
            )

        message += f"🔢 Commits: {commit_count}\n\n"

        if commit_count > 0:
            max_commits = min(5, commit_count)
            message += "*Latest Commits:*\n"

            for i in range(max_commits):
                commit = payload["commits"][i]
                short_hash = commit["id"][:7]
                commit_url = f"{repo_url}/commit/{commit['id']}"
                commit_url_escaped = escape_md_v2(commit_url)

                commit_msg = commit["message"].split("\n")[0]
                if len(commit_msg) > 50:
                    commit_msg = commit_msg[:47] + "..."
                commit_msg = escape_md_v2(commit_msg)

                author = commit["author"]["name"]
                author_username = commit["author"].get("username", author)
                author_url = f"https://github.com/{author_username}"
                author_name_escaped = escape_md_v2(author)
                author_url_escaped = escape_md_v2(author_url)

                message += f"• [`{short_hash}`]({commit_url_escaped}) {commit_msg} \\- [_{author_name_escaped}_]({author_url_escaped})\n"

            if commit_count > max_commits:
                message += f"_\\+ {commit_count - max_commits} more commits_\n"

        if commit_count == 1 and "head_commit" in payload and payload["head_commit"]:
            head_commit = payload["head_commit"]
            added = len(head_commit.get("added", []))
            modified = len(head_commit.get("modified", []))
            removed = len(head_commit.get("removed", []))

            if added > 0 or modified > 0 or removed > 0:
                message += "\n📊 *Changes:* "
                changes = []
                if added > 0:
                    changes.append(f"➕ {added} added")
                if modified > 0:
                    changes.append(f"📝 {modified} modified")
                if removed > 0:
                    changes.append(f"➖ {removed} removed")
                message += ", ".join(changes)

                if modified > 0 and len(head_commit.get("modified", [])) > 0:
                    files = head_commit.get("modified", [])
                    message += "\n\n*Modified files:*"
                    for i, file in enumerate(files[:3]):
                        file_url = f"{repo_url}/blob/{head_commit['id']}/{file}"
                        file_escaped = escape_md_v2(file)
                        file_url_escaped = escape_md_v2(file_url)
                        message += f"\n• [`{file_escaped}`]({file_url_escaped})"
                    if len(files) > 3:
                        message += f"\n_\\+ {len(files) - 3} more files_"

        message += f"\n\n[🔍 View All Changes]({compare_url_escaped})"

        return message
    except Exception as e:
        print(f"Error formatting push message: {str(e)}")
        return f"New push to repository {escape_md_v2(payload.get('repository', {}).get('full_name', 'unknown'))}"


def handle_pull_request(payload: dict) -> str:
    try:
        action = payload["action"]
        pr = payload["pull_request"]

        # Basic PR information
        repo = pr["base"]["repo"]["name"]
        repo_url = pr["base"]["repo"]["html_url"]
        pr_number = pr["number"]
        title = pr["title"]
        body = pr["body"] if pr["body"] else "No description provided"
        user = pr["user"]["login"]
        user_url = pr["user"]["html_url"]
        pr_url = pr["html_url"]

        # Branch information
        head_branch = pr["head"]["ref"]
        base_branch = pr["base"]["ref"]

        # State information
        is_merged = pr.get("merged", False)
        is_draft = pr.get("draft", False)

        # PR stats
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        changed_files = pr.get("changed_files", 0)

        # Escape values - with better handling
        title_escaped = escape_md_v2(title)
        repo_escaped = escape_md_v2(repo)
        repo_url_escaped = escape_md_v2(repo_url)
        user_escaped = escape_md_v2(user)
        user_url_escaped = escape_md_v2(user_url)
        pr_url_escaped = escape_md_v2(pr_url)
        head_branch_escaped = escape_md_v2(head_branch)
        base_branch_escaped = escape_md_v2(base_branch)

        # Draft indicator
        draft_text = " \\(Draft\\)" if is_draft else ""

        if action == "opened":
            # Simplify the description handling to avoid formatting issues
            short_body = body
            if len(body) > 100:  # Keep description shorter to reduce formatting issues
                short_body = body[:97] + "..."
            body_escaped = escape_md_v2(short_body)

            # Create labels string if labels exist
            labels_text = ""
            if pr.get("labels") and len(pr["labels"]) > 0:
                label_names = []
                for label in pr["labels"]:
                    name = escape_md_v2(label["name"])
                    label_names.append(f"`{name}`")
                labels_text = f"\n🏷 Labels: {', '.join(label_names)}"

            # Stats text for opened PRs
            stats_text = (
                f"\n📊 Changes: \\+{additions}, \\-{deletions}, {changed_files} files"
            )

            # Construct message with focus on essential information
            message = (
                f"🔀 *New Pull Request{draft_text}*\n\n"
                f"📝 Title: *{title_escaped}*\n"
                f"📂 Repository: [{repo_escaped}]({repo_url_escaped})\n"
                f"👤 Created by: [{user_escaped}]({user_url_escaped})\n"
                f"🔀 Branches: `{head_branch_escaped}` → `{base_branch_escaped}`"
                f"{stats_text}"
                f"{labels_text}"
                f"💬 Description: {body_escaped}\n\n"
                f"[View Pull Request]({pr_url_escaped})"
            )

        elif action == "closed":
            # Different message for merged vs. closed without merging
            if is_merged:
                # Check for merger info
                merger_text = ""
                if pr.get("merged_by"):
                    merger = pr["merged_by"]
                    merger_name = escape_md_v2(merger["login"])
                    merger_text = f"\n🧙 Merged by: {merger_name}"

                message = (
                    f"✅ *Pull Request Merged*\n\n"
                    f"📝 Title: *{title_escaped}*\n"
                    f"📂 Repository: [{repo_escaped}]({repo_url_escaped})\n"
                    f"👤 Author: [{user_escaped}]({user_url_escaped})\n"
                    f"🔢 PR\\#{pr_number}\n"
                    f"🔀 `{head_branch_escaped}` → `{base_branch_escaped}`"
                    f"{merger_text}\n\n"
                    f"[View Merged PR]({pr_url_escaped})"
                )
            else:
                message = (
                    f"❌ *Pull Request Closed*\n\n"
                    f"📝 Title: *{title_escaped}*\n"
                    f"📂 Repository: [{repo_escaped}]({repo_url_escaped})\n"
                    f"👤 Author: [{user_escaped}]({user_url_escaped})\n"
                    f"🔢 PR\\#{pr_number}\n\n"
                    f"[View Closed PR]({pr_url_escaped})"
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
        title = issue["title"]
        user = issue["user"]["login"]
        url = issue["html_url"]

        if action == "opened":
            description = issue["body"] if issue["body"] else "No description provided"
            if len(description) > 300:
                description = description[:297] + "..."

            labels_text = ""
            if issue["labels"]:
                label_names = [
                    f"`{escape_md_v2(label['name'])}`" for label in issue["labels"]
                ]
                labels_text = f"\n🏷 Labels: {', '.join(label_names)}"

            assignee_text = ""
            if (
                "assignees" in issue
                and issue["assignees"]
                and len(issue["assignees"]) > 0
            ):
                assignees = [
                    f"[{escape_md_v2(a['login'])}]({a['html_url']})"
                    for a in issue["assignees"]
                ]
                assignee_text = f"\n👤 Assigned to: {', '.join(assignees)}"
            else:
                assignee_text = "\n👤 No one assigned yet"

            title_escaped = escape_md_v2(title)
            repo_name_escaped = escape_md_v2(payload["repository"]["name"])
            user_escaped = escape_md_v2(user)
            description_escaped = escape_md_v2(description)

            message = (
                f"🔔 *New Issue Opened*\n\n"
                f"📝 Title: *{title_escaped}*\n"
                f"📂 Repository: [{repo_name_escaped}]({payload['repository']['html_url']})\n"
                f"👤 Created by: [{user_escaped}]({issue['user']['html_url']})"
                f"{labels_text}"
                f"{assignee_text}\n\n"
                f"💬 Description:\n"
                f"{description_escaped}\n\n"
                f"[View Issue \\→]({url})"
            )
        elif action == "closed":
            message = (
                f"🔒 *Issue Closed*\n\n"
                f"📝 Title: *{escape_md_v2(title)}*\n"
                f"📂 Repository: [{escape_md_v2(repo)}]({payload['repository']['html_url']})\n"
                f"👤 Closed by: [{escape_md_v2(user)}]({issue['user']['html_url']})\n\n"
                f"[View Issue \\→]({url})"
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
