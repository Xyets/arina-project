from flask import Blueprint, render_template, session, redirect, url_for, jsonify, request
from functools import wraps
import requests
import json
from datetime import datetime

fc2_bp = Blueprint("fc2", __name__)

# -------------------- AUTH --------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("panel.login"))
        return f(*args, **kwargs)
    return wrapper

# -------------------- COLORS --------------------
USER_COLORS = {}

def get_color_for_user(user_id):
    if user_id not in USER_COLORS:
        import random
        USER_COLORS[user_id] = f"hsl({random.randint(0,360)}, 70%, 70%)"
    return USER_COLORS[user_id]

# -------------------- TRANSLATION --------------------
def translate_text(text):
    try:
        r = requests.post(
            "https://libretranslate.com/translate",
            json={
                "q": text,
                "source": "ja",
                "target": "ru",
                "format": "text"
            },
            timeout=5
        )
        data = r.json()
        return data.get("translatedText", "")
    except:
        return ""

# -------------------- PAGE --------------------
@fc2_bp.route("/fc2_comments")
@login_required
def fc2_comments_page():
    return render_template("fc2_comments.html")

# -------------------- API --------------------
FC2_CHANNEL = "42811971"
FC2_TOKEN = "ТВОЙ_ТОКЕН"

@fc2_bp.route("/fc2_api")
def fc2_api():
    last = request.args.get("last", "-1")

    url = f"https://live.fc2.com/api/getChannelComment.php?channel_id=42811971&token=dcb06e8d24b06d88&last_comment_index=-1"

    try:
        r = requests.get(url, timeout=5)
        data = r.json()
    except Exception as e:
        return jsonify({"error": str(e)})

    comments = data.get("comment_list", [])
    enhanced = []

    for c in comments:
        text = c.get("comment", "")
        user_id = c.get("user_id", "unknown")

        translated = translate_text(text) if text else ""
        color = get_color_for_user(user_id)

        enhanced.append({
            "comment": text,
            "translated": translated,
            "user_id": user_id,
            "time": c.get("time"),
            "index": c.get("index"),
            "color": color
        })

        with open("fc2_comments.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(enhanced[-1], ensure_ascii=False) + "\n")

    return jsonify({"comments": enhanced})
