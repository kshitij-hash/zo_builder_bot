GITHUB_WEIGHTS = {"commits": 1, "prs": 5, "issues": 2}
TELEGRAM_WEIGHTS = {"messages": 0.1, "replies": 1}
NOMINATION_WEIGHT = 3  # Weight for each nomination received
W_G = 0.6  # Overall GitHub weight
W_T = 0.3  # Overall Telegram weight
W_N = 0.1  # Overall Nominations weight

NORMALIZATION_THRESHOLD = 5  # Minimum users required for normalization
# Reference points for scoring when below threshold
MAX_EXPECTED_GITHUB = 50  # Maximum expected GitHub contribution score
MAX_EXPECTED_TELEGRAM = 200  # Maximum expected Telegram activity score  
MAX_EXPECTED_NOMINATIONS = 10  # Maximum expected nominations

def compute_subscore(contributions, weights):
    return sum(contributions[k] * weights.get(k, 0) for k in contributions)


def normalize_scores(scores):
    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0
    if max_score == min_score:
        return [1.0] * len(scores) if scores else []  # avoid division by zero
    return [(s - min_score) / (max_score - min_score) for s in scores] if scores else []


def compute_builder_scores(user_data):
    github_raw_scores = []
    telegram_raw_scores = []
    nomination_scores = []

    for user in user_data:
        g_score = compute_subscore(user.get("github_contributions", {}), GITHUB_WEIGHTS)
        t_score = compute_subscore(user.get("telegram_activity", {}), TELEGRAM_WEIGHTS)
        n_score = user.get("nominations_received", 0) * NOMINATION_WEIGHT
        
        github_raw_scores.append(g_score)
        telegram_raw_scores.append(t_score)
        nomination_scores.append(n_score)

    # Check if we have enough users for normalization
    if len(user_data) >= NORMALIZATION_THRESHOLD:
        # Use relative normalization when we have enough users
        github_norm = normalize_scores(github_raw_scores)
        telegram_norm = normalize_scores(telegram_raw_scores)
        nomination_norm = normalize_scores(nomination_scores)
    else:
        # Use absolute scoring with reference points when we have few users
        github_norm = [min(1.0, score / MAX_EXPECTED_GITHUB) for score in github_raw_scores]
        telegram_norm = [min(1.0, score / MAX_EXPECTED_TELEGRAM) for score in telegram_raw_scores]
        nomination_norm = [min(1.0, score / MAX_EXPECTED_NOMINATIONS) for score in nomination_scores]

    builder_scores = []
    for i, user in enumerate(user_data):
        if i < len(github_norm) and i < len(telegram_norm) and i < len(nomination_norm):
            score = W_G * github_norm[i] + W_T * telegram_norm[i] + W_N * nomination_norm[i]
            builder_scores.append(
                {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "builder_score": round(score * 100, 2),  # Scale to 0-100
                }
            )

    return sorted(builder_scores, key=lambda x: x["builder_score"], reverse=True)
