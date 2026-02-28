from pyrogram import Client

api_id = int(input("Enter API_ID: "))
api_hash = input("Enter API_HASH: ")

with Client("my_account", api_id, api_hash) as app:
    print("\nYour New Session String:\n")
    print(app.export_session_string())
with Client("my_account", api_id, api_hash) as app:
    print("\nYour New Session String:\n")
    print(app.export_session_string())
DEFAULT_LIMIT = 1000  # Card Scrapping Limit For Everyone
PREMIUM_LIMIT = 5000  # Card Scrapping Limit For Premium Users

# Cooldown settings (in seconds)
COOLDOWN_FREE = 10  # Cooldown for Free users
COOLDOWN_TRIAL = 10  # Cooldown for Trial users

# Credit cost per command
CREDIT_COST = 2  # Credits deducted for each successful command
