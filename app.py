import firebase_admin
from firebase_admin import credentials, firestore
import requests
import json
import os
import sys
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

def initialize_firebase():
    # Try environment variable first (most secure for cloud)
    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        try:
            cred_dict = json.loads(service_account_json)
            cred_obj = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred_obj)
            return firestore.client()
        except Exception as e:
            print(f"Failed to initialize with environment variable: {e}")
    
    # Fallback to file paths
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

    print(f"Synced users. Created {created_count}, deleted {deleted_count}. Total API users: {len(api_set)}")

def get_leaderboard_data():
    players = db.collection("players").order_by("score", direction=firestore.Query.DESCENDING).stream()
    leaderboard = []
    for i, player in enumerate(players, 1):
        data = player.to_dict()
        leaderboard.append({
            'rank': i,
            'name': data['name'],
            'score': data['score']
        })
    return leaderboard

def background_sync():
    """Background thread for syncing users from API"""
    while True:
        try:
            sync_users_from_api()
            time.sleep(30)  # Sync every 30 seconds
        except Exception as e:
            print(f"Error in background sync: {e}")
            time.sleep(30)

# Start background sync thread
sync_thread = threading.Thread(target=background_sync, daemon=True)
sync_thread.start()

# === Flask Routes ===

@app.route('/')
def index():
    return redirect(url_for('public_leaderboard'))

@app.route('/admin')
def admin():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    leaderboard = get_leaderboard_data()
    return render_template('admin.html', leaderboard=leaderboard)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            session.permanent = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Logged out successfully!', 'info')
    return redirect(url_for('login'))

@app.route('/update_score', methods=['POST'])
def update_score():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    player_name = data.get('player_name')
    score_change = data.get('score_change')
    
    if not player_name or score_change is None:
        return jsonify({'error': 'Missing player_name or score_change'}), 400
    
    try:
        player_ref = db.collection("players").document(player_name)
        player_ref.update({
            "score": firestore.Increment(score_change)
        })
        return jsonify({'success': True, 'message': f'Updated {player_name}\'s score by {score_change}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_leaderboard')
def get_leaderboard():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    leaderboard = get_leaderboard_data()
    return jsonify(leaderboard)

@app.route('/public_leaderboard')
def public_leaderboard():
    """Public leaderboard view (no login required)"""
    leaderboard = get_leaderboard_data()
    return render_template('public_leaderboard.html', leaderboard=leaderboard)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
