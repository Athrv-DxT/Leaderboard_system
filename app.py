import firebase_admin
from firebase_admin import credentials, firestore
import requests
import json
import os
import sys
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import timedelta, datetime
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# === CACHING SYSTEM ===
leaderboard_cache = {
    'data': None,
    'timestamp': None,
    'lock': threading.Lock(),
    'ttl': 300  # 5 minutes cache TTL
}

# Rate limiting for Firestore queries
firestore_rate_limiter = {
    'last_query': None,
    'min_interval': 10,  # Minimum 10 seconds between queries
    'lock': threading.Lock()
}

# Sync control
sync_control = {
    'enabled': True,
    'interval': 300,  # Sync every 5 minutes instead of 30 seconds
    'last_sync': None,
    'lock': threading.Lock()
}

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

def rate_limited_firestore_query(query_func, *args, **kwargs):
    """Rate-limited wrapper for Firestore queries"""
    with firestore_rate_limiter['lock']:
        now = time.time()
        if firestore_rate_limiter['last_query']:
            time_since_last = now - firestore_rate_limiter['last_query']
            if time_since_last < firestore_rate_limiter['min_interval']:
                sleep_time = firestore_rate_limiter['min_interval'] - time_since_last
                print(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        try:
            result = query_func(*args, **kwargs)
            firestore_rate_limiter['last_query'] = time.time()
            return result
        except Exception as e:
            if "quota" in str(e).lower() or "resource exhausted" in str(e).lower():
                print(f"Quota exhausted. Disabling sync and using cache only.")
                sync_control['enabled'] = False
                # Return cached data if available
                if leaderboard_cache['data']:
                    return leaderboard_cache['data']
            raise e

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
    def query():
        player_docs = db.collection("players").stream()
        names = []
        for doc in player_docs:
            data = doc.to_dict() or {}
            name = data.get("name") or doc.id
            if name:
                names.append(str(name))
        return names
    
    return rate_limited_firestore_query(query)

def sync_users_from_api():
    with sync_control['lock']:
        if not sync_control['enabled']:
            print("Sync disabled due to quota exhaustion")
            return
        
        now = time.time()
        if sync_control['last_sync']:
            time_since_last = now - sync_control['last_sync']
            if time_since_last < sync_control['interval']:
                return  # Skip if too soon
    
    try:
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

        # Create missing players (rate limited)
        for username in to_create:
            if created_count >= 5:  # Limit batch operations
                break
            doc_ref = players_collection.document(username)
            doc_ref.set({
                "name": username,
                "score": 0
            })
            created_count += 1
            time.sleep(1)  # Throttle individual operations

        # Delete players no longer present in API (rate limited)
        for username in to_delete:
            if deleted_count >= 5:  # Limit batch operations
                break
            doc_ref = players_collection.document(username)
            doc_ref.delete()
            deleted_count += 1
            time.sleep(1)  # Throttle individual operations

        sync_control['last_sync'] = time.time()
        print(f"Synced users. Created {created_count}, deleted {deleted_count}. Total API users: {len(api_set)}")

    except Exception as e:
        print(f"Sync failed: {e}")
        if "quota" in str(e).lower():
            sync_control['enabled'] = False

def get_leaderboard_data():
    """Get leaderboard data with intelligent caching"""
    with leaderboard_cache['lock']:
        now = datetime.now()
        
        # Check if cache is still valid
        if (leaderboard_cache['data'] and 
            leaderboard_cache['timestamp'] and 
            (now - leaderboard_cache['timestamp']).total_seconds() < leaderboard_cache['ttl']):
            print("Returning cached leaderboard data")
            return leaderboard_cache['data']
        
        # Need fresh data - check if sync is disabled
        if not sync_control['enabled']:
            if leaderboard_cache['data']:
                print("Sync disabled, returning stale cache")
                return leaderboard_cache['data']
            else:
                # Emergency fallback
                return [{'rank': 1, 'name': 'Service Temporarily Unavailable', 'score': 0}]
        
        try:
            # Fetch fresh data with rate limiting
            def query():
                players = db.collection("players").order_by("score", direction=firestore.Query.DESCENDING).stream()
                leaderboard = []
                for i, player in enumerate(players, 1):
                    data = player.to_dict()
                    score = data.get('score', 0)
                    # Ensure score is properly converted to integer
                    try:
                        score = int(score)
                    except (ValueError, TypeError):
                        score = 0
                    
                    leaderboard.append({
                        'rank': i,
                        'name': data.get('name', 'Unknown'),
                        'score': score
                    })
                
                # Double-check sorting by score (highest first)
                leaderboard.sort(key=lambda x: x['score'], reverse=True)
                
                # Update ranks after sorting
                for i, player in enumerate(leaderboard):
                    player['rank'] = i + 1
                
                return leaderboard
            
            fresh_data = rate_limited_firestore_query(query)
            
            # Update cache
            leaderboard_cache['data'] = fresh_data
            leaderboard_cache['timestamp'] = now
            
            print(f"Fresh leaderboard data fetched, {len(fresh_data)} players")
            return fresh_data
            
        except Exception as e:
            print(f"Error fetching leaderboard: {e}")
            # Return cached data if available, even if stale
            if leaderboard_cache['data']:
                print("Error occurred, returning stale cache")
                return leaderboard_cache['data']
            
            # Ultimate fallback
            return [{'rank': 1, 'name': 'Service Error', 'score': 0}]

def background_sync():
    """Background thread for syncing users from API - with much longer intervals"""
    while True:
        try:
            if sync_control['enabled']:
                sync_users_from_api()
            time.sleep(sync_control['interval'])  # 5 minutes instead of 30 seconds
        except Exception as e:
            print(f"Error in background sync: {e}")
            time.sleep(sync_control['interval'])

# Start background sync thread with reduced frequency
if not os.environ.get('TESTING'):
    sync_thread = threading.Thread(target=background_sync, daemon=True)
    sync_thread.start()
    print(f"Background sync thread started (interval: {sync_control['interval']}s)")

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
    
    if not sync_control['enabled']:
        return jsonify({'error': 'Service temporarily unavailable due to quota limits'}), 503
    
    data = request.get_json()
    player_name = data.get('player_name')
    score_change = data.get('score_change')
    
    if not player_name or score_change is None:
        return jsonify({'error': 'Missing player_name or score_change'}), 400
    
    try:
        def update():
            player_ref = db.collection("players").document(player_name)
            player_ref.update({
                "score": firestore.Increment(score_change)
            })
        
        rate_limited_firestore_query(update)
        
        # Invalidate cache to force refresh
        with leaderboard_cache['lock']:
            leaderboard_cache['timestamp'] = None
        
        return jsonify({'success': True, 'message': f'Updated {player_name}\'s score by {score_change}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_leaderboard')
def get_leaderboard():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    leaderboard = get_leaderboard_data()
    return jsonify(leaderboard)

@app.route('/api/leaderboard')
def api_leaderboard():
    """Public API endpoint for leaderboard data"""
    leaderboard = get_leaderboard_data()
    return jsonify(leaderboard)

@app.route('/public_leaderboard')
def public_leaderboard():
    """Public leaderboard view (no login required)"""
    leaderboard = get_leaderboard_data()
    return render_template('public_leaderboard.html', leaderboard=leaderboard)

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    return jsonify({
        'status': 'healthy' if sync_control['enabled'] else 'degraded',
        'message': 'FunFinity Leaderboard is running',
        'cache_age': (datetime.now() - leaderboard_cache['timestamp']).total_seconds() if leaderboard_cache['timestamp'] else None,
        'sync_enabled': sync_control['enabled']
    })

@app.route('/admin/toggle_sync', methods=['POST'])
def toggle_sync():
    """Emergency sync toggle for admin"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with sync_control['lock']:
        sync_control['enabled'] = not sync_control['enabled']
    
    return jsonify({'sync_enabled': sync_control['enabled']})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on port {port}")
    print(f"Sync interval: {sync_control['interval']} seconds")
    print(f"Cache TTL: {leaderboard_cache['ttl']} seconds")
    app.run(host='0.0.0.0', port=port, debug=False)