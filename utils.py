import re


def highlight_concepts(html, concepts=None):
    """Highlight role headers and key concepts in the text"""
    # Highlight role headers first
    html = re.sub(
        r"\*\*You said:\*\*",
        r"<div class='you-said'><strong>You said:</strong></div>",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"\*\*ChatGPT said:\*\*",
        r"<div class='chatgpt-said'><strong>ChatGPT said:</strong></div>",
        html,
        flags=re.IGNORECASE,
    )

    # Highlight key concepts
    if concepts:
        for word in concepts:
            pattern = r"\b(" + re.escape(word) + r")\b"
            html = re.sub(
                pattern, r"<span class='concept'>\1</span>", html, flags=re.IGNORECASE
            )

    return html
