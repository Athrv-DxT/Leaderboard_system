import firebase_admin
from firebase_admin import credentials, firestore
import requests
import json
import os
import sys
import time

def initialize_firebase():
    # Prefer GOOGLE_APPLICATION_CREDENTIALS if provided
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    try_paths = []
    if creds_path and os.path.isfile(creds_path):
        try_paths.append(creds_path)
    # Fallback to local serviceAccountKey.json
    try_paths.append("serviceAccountKey.json")

    last_err = None
    for path in try_paths:
        try:
            cred_obj = credentials.Certificate(path)
            firebase_admin.initialize_app(cred_obj)
            return firestore.client()
        except Exception as e:
            last_err = e

    print("Failed to initialize Firebase Admin SDK.")
    print("Reason:", last_err)
    print(
        "Please provide a valid Service Account JSON file (not the web SDK config).\n"
        "Options:\n"
        "1) Set env var GOOGLE_APPLICATION_CREDENTIALS to point to your service account JSON.\n"
        "2) Place the JSON at 'serviceAccountKey.json' in this directory.\n"
        "Get it from Firebase Console → Project Settings → Service accounts → Generate new private key."
    )
    sys.exit(1)

# Initialize Firebase
db = initialize_firebase()

# === External Users API Configuration ===
API_URL = os.environ.get("API_URL", "https://web-production-3b67.up.railway.app/api/users")
API_KEY = os.environ.get("API_KEY", "1f8c3f7c0b9d4f25a6b1e2c93d7f48aa3f9c1e7b5a64c2d1e0f3a8b7c6d5e4f1")

# === Users API Integration ===
def fetch_usernames_from_api():
    try:
        response = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
        response.raise_for_status()
        all_users = response.json()
    except Exception as e:
        print(f"Failed to fetch users: {e}")
        return []

    usernames = []

    if isinstance(all_users, list):
        for user in all_users:
            if isinstance(user, dict):
                if user.get('role') == 'user':
                    username = (
                        user.get('username')
                        or user.get('name')
                        or user.get('user_name')
                        or user.get('email')
                    )
                    if username:
                        usernames.append(str(username))
            elif isinstance(user, str):
                try:
                    user_dict = json.loads(user)
                    if user_dict.get('role') == 'user':
                        username = (
                            user_dict.get('username')
                            or user_dict.get('name')
                            or user_dict.get('user_name')
                            or user_dict.get('email')
                        )
                        if username:
                            usernames.append(str(username))
                except Exception:
                    continue
    elif isinstance(all_users, dict):
        for _, value in all_users.items():
            if isinstance(value, list):
                for user in value:
                    if isinstance(user, dict) and user.get('role') == 'user':
                        username = (
                            user.get('username')
                            or user.get('name')
                            or user.get('user_name')
                            or user.get('email')
                        )
                        if username:
                            usernames.append(str(username))

    return usernames

def _get_current_player_names_from_firestore():
    player_docs = db.collection("players").stream()
    names = []
    for doc in player_docs:
        data = doc.to_dict() or {}
        name = data.get("name") or doc.id
        if name:
            names.append(str(name))
    return names

def sync_users_from_api():
    # Fetch current usernames from API (source of truth)
    usernames = fetch_usernames_from_api()
    if usernames is None:
        usernames = []
    api_set = set(usernames)

    # Fetch current players in Firestore
    current_players = _get_current_player_names_from_firestore()
    fs_set = set(current_players)

    players_collection = db.collection("players")

    # Determine diffs
    to_create = api_set - fs_set
    to_delete = fs_set - api_set

    created_count = 0
    deleted_count = 0

    # Create missing players
    for username in to_create:
        doc_ref = players_collection.document(username)
        doc_ref.set({
            "name": username,
            "score": 0
        })
        created_count += 1

    # Delete players no longer present in API
    for username in to_delete:
        doc_ref = players_collection.document(username)
        doc_ref.delete()
        deleted_count += 1

    print(
        f"Synced users. Created {created_count}, deleted {deleted_count}. Total API users: {len(api_set)}"
    )

def clear_console():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass

def refresh_loop(interval_seconds: int = 2):
    print(f"Starting refresh loop. Syncing from API every {interval_seconds} seconds. Press Ctrl+C to stop.")
    while True:
        try:
            sync_users_from_api()
            clear_console()
            get_leaderboard()
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nStopped refresh loop.")
            break
        except Exception as e:
            # Log and continue
            print(f"Error during refresh: {e}")
            time.sleep(interval_seconds)

# Register new player (first login)
def register_player(player_name):
    db.collection("players").document(player_name).set({
        "name": player_name,
        "score": 0
    })

# Update score when player plays
def update_score(player_name, points):
    player_ref = db.collection("players").document(player_name)
    player_ref.update({
        "score": firestore.Increment(points)
    })

# Get current leaderboard
def get_leaderboard():
    players = db.collection("players").order_by("score", direction=firestore.Query.DESCENDING).stream()
    print("\n=== Leaderboard ===")
    for i, player in enumerate(players, 1):
        data = player.to_dict()
        print(f"{i}. {data['name']} - {data['score']}")

# Run sync from API then display leaderboard
if __name__ == "__main__":
    refresh_loop(2)
