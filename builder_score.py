GITHUB_WEIGHTS = {"commits": 1, "prs": 5, "issues": 2}
TELEGRAM_WEIGHTS = {"messages": 0.1, "replies": 1}
W_G = 0.7  # Overall GitHub weight
W_T = 0.3  # Overall Telegram weight


def compute_subscore(contributions, weights):
    return sum(contributions[k] * weights.get(k, 0) for k in contributions)


def normalize_scores(scores):
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [1.0] * len(scores)  # avoid division by zero
    return [(s - min_score) / (max_score - min_score) for s in scores]


def compute_builder_scores(user_data):
    github_raw_scores = []
    telegram_raw_scores = []

    for user in user_data:
        g_score = compute_subscore(user.get("github_contributions"), GITHUB_WEIGHTS)
        t_score = compute_subscore(user.get("telegram_activity"), TELEGRAM_WEIGHTS)
        github_raw_scores.append(g_score)
        telegram_raw_scores.append(t_score)

    github_norm = normalize_scores(github_raw_scores)
    telegram_norm = normalize_scores(telegram_raw_scores)

    builder_scores = []
    for i, user in enumerate(user_data):
        score = W_G * github_norm[i] + W_T * telegram_norm[i]
        builder_scores.append(
            {
                "user_id": user["user_id"],
                "username": user["username"],
                "builder_score": round(score * 100, 2),  # Optional: scale to 0–100
            }
        )

    return sorted(builder_scores, key=lambda x: x["builder_score"], reverse=True)
