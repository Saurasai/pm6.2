# Prompt templates for different platforms
PROMPT_TEMPLATES = {
    "twitter": (
        "Write 3 separate Twitter posts under 280 characters each about '{topic}'. "
        "Use a {tone} tone with emojis and the hashtags {hashtags}. "
        "Output only the posts, numbered 1, 2, and 3, without any extra explanation or introduction."
    ),
    "linkedin": (
        "Write 3 professional LinkedIn posts about '{topic}'. "
        "Include the insight '{insight}'. Use a {tone} tone. "
        "Output only the posts, numbered 1, 2, and 3, with no extra introduction."
    ),
    "instagram": (
        "Write 3 Instagram captions about '{topic}' with a {tone} tone and relevant emojis. "
        "Include a call to action in each. "
        "Output only the captions, numbered 1, 2, and 3, without extra text."
    )
}

# Available tone options
TONE_OPTIONS = [
    "casual", "professional", "humorous", "enthusiastic",
    "bold", "friendly", "sarcastic", "inspirational"
]