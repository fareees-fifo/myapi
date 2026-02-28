from flask import Flask, request
import requests
import os

app = Flask(__name__)

TOKEN = "6899797841:AAHsicM8rF-kIiGfKP87xKC6k6TswwlGzH0"

@app.route("/")
def home():
    return "Bot is running successfully!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        reply = "أهلا بك 👋"

        requests.post(
            f"https://api.telegram.org/bot{6899797841:AAHsicM8rF-kIiGfKP87xKC6k6TswwlGzH0}/sendMessage",
            json={"chat_id": chat_id, "text": reply}
        )

    return "ok"

if name == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

