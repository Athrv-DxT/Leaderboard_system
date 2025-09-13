import sqlite3
import requests
import json
import os
import sys
import time
import threading
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import timedelta, datetime
import logging
import atexit

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Admin credentials (in production, use environment variables)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# === DATABASE CONFIGURATION ===
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'leaderboard.db')

# === CACHING SYSTEM ===
leaderboard_cache = {
    'data': None,
    'timestamp': None,
    'lock': threading.Lock(),
    'ttl': 30  # 30 seconds cache TTL for real-time updates
}

# Rate limiting for API calls
api_rate_limiter = {
    'last_query': None,
    'min_interval': 2,  # Minimum 2 seconds between API calls
    'lock': threading.Lock()
}

# Sync control
sync_control = {
    'enabled': True,
    'interval': 3,  # Sync every 3 seconds as requested
    'last_sync': None,
    'lock': threading.Lock()
}

def initialize_database():
    """Initialize SQLite database with players table"""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS players (
            name TEXT PRIMARY KEY,
            score INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_score ON players(score DESC)
    ''')
    conn.commit()
    return conn

def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Initialize database
db_conn = initialize_database()
if db_conn:
    db_conn.close()

# Register cleanup function
def cleanup_database():
    if 'db_conn' in globals() and db_conn:
        db_conn.close()

atexit.register(cleanup_database)

# === External Users API Configuration ===
API_URL = os.environ.get("API_URL", "https://web-production-3b67.up.railway.app/api/users")
API_KEY = os.environ.get("API_KEY", "1f8c3f7c0b9d4f25a6b1e2c93d7f48aa3f9c1e7b5a64c2d1e0f3a8b7c6d5e4f1")

def rate_limited_api_call():
    """Rate-limited wrapper for API calls"""
    with api_rate_limiter['lock']:
        now = time.time()
        if api_rate_limiter['last_query']:
            time_since_last = now - api_rate_limiter['last_query']
            if time_since_last < api_rate_limiter['min_interval']:
                sleep_time = api_rate_limiter['min_interval'] - time_since_last
                print(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        try:
            response = requests.get(API_URL, headers={"X-API-Key": API_KEY}, timeout=15)
            response.raise_for_status()
            api_rate_limiter['last_query'] = time.time()
            return response.json()
        except Exception as e:
            print(f"API call failed: {e}")
            return None

def fetch_usernames_from_api():
    """Fetch usernames from API using rate limiting"""
    all_users = rate_limited_api_call()
    if not all_users:
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

def _get_current_player_names_from_db():
    """Get current player names from SQLite database"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.execute("SELECT name FROM players")
        names = [row['name'] for row in cursor.fetchall()]
        return names
    except Exception as e:
        print(f"Error fetching player names: {e}")
        return []
    finally:
        conn.close()

def sync_users_from_api():
    with sync_control['lock']:
        if not sync_control['enabled']:
            print("Sync disabled")
            return
        
        now = time.time()
        if sync_control['last_sync']:
            time_since_last = now - sync_control['last_sync']
            if time_since_last < sync_control['interval']:
                return  # Skip if too soon
    
    try:
        # Fetch current usernames from API (source of truth)
        usernames = fetch_usernames_from_api()
        if not usernames:
            return
        api_set = set(usernames)

        # Fetch current players in database
        current_players = _get_current_player_names_from_db()
        db_set = set(current_players)

        # Determine diffs
        to_create = api_set - db_set
        to_delete = db_set - api_set

        conn = get_db_connection()
        if not conn:
            return

        try:
            created_count = 0
            deleted_count = 0

            # Create missing players
            for username in to_create:
                conn.execute(
                    "INSERT OR IGNORE INTO players (name, score) VALUES (?, ?)",
                    (username, 0)
                )
                created_count += 1

            # Delete players no longer present in API
            for username in to_delete:
                conn.execute("DELETE FROM players WHERE name = ?", (username,))
                deleted_count += 1

            conn.commit()
            sync_control['last_sync'] = time.time()
            print(f"Synced users. Created {created_count}, deleted {deleted_count}. Total API users: {len(api_set)}")

        finally:
            conn.close()

    except Exception as e:
        print(f"Sync failed: {e}")

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
            # Fetch fresh data from SQLite
            conn = get_db_connection()
            if not conn:
                if leaderboard_cache['data']:
                    return leaderboard_cache['data']
                return [{'rank': 1, 'name': 'Database Error', 'score': 0}]
            
            try:
                cursor = conn.execute(
                    "SELECT name, score FROM players ORDER BY score DESC"
                )
                players = cursor.fetchall()
                
                leaderboard = []
                for i, player in enumerate(players, 1):
                    score = player['score'] or 0
                    # Ensure score is properly converted to integer
                    try:
                        score = int(score)
                    except (ValueError, TypeError):
                        score = 0
                    
                    leaderboard.append({
                        'rank': i,
                        'name': player['name'] or 'Unknown',
                        'score': score
                    })
                
                # Update cache
                leaderboard_cache['data'] = leaderboard
                leaderboard_cache['timestamp'] = now
                
                print(f"Fresh leaderboard data fetched, {len(leaderboard)} players")
                return leaderboard
                
            finally:
                conn.close()
            
        except Exception as e:
            print(f"Error fetching leaderboard: {e}")
            # Return cached data if available, even if stale
            if leaderboard_cache['data']:
                print("Error occurred, returning stale cache")
                return leaderboard_cache['data']
            
            # Ultimate fallback
            return [{'rank': 1, 'name': 'Service Error', 'score': 0}]

def background_sync():
    """Background thread for syncing users from API every 3 seconds"""
    while True:
        try:
            if sync_control['enabled']:
                sync_users_from_api()
            time.sleep(sync_control['interval'])  # 3 seconds as requested
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
        return jsonify({'error': 'Service temporarily unavailable'}), 503
    
    data = request.get_json()
    player_name = data.get('player_name')
    score_change = data.get('score_change')
    
    if not player_name or score_change is None:
        return jsonify({'error': 'Missing player_name or score_change'}), 400
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            # Update score using SQLite
            conn.execute(
                "UPDATE players SET score = score + ?, last_updated = CURRENT_TIMESTAMP WHERE name = ?",
                (score_change, player_name)
            )
            conn.commit()
            
            # Invalidate cache to force refresh
            with leaderboard_cache['lock']:
                leaderboard_cache['timestamp'] = None
            
            return jsonify({'success': True, 'message': f'Updated {player_name}\'s score by {score_change}'})
        finally:
            conn.close()
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
    cache_age = None
    if leaderboard_cache['timestamp']:
        cache_age = (datetime.now() - leaderboard_cache['timestamp']).total_seconds()
    
    return jsonify({
        'status': 'healthy' if sync_control['enabled'] else 'degraded',
        'message': 'FunFinity Leaderboard is running',
        'cache_age': cache_age,
        'sync_enabled': sync_control['enabled'],
        'database': 'SQLite',
        'sync_interval': sync_control['interval']
    })

@app.route('/admin/toggle_sync', methods=['POST'])
def toggle_sync():
    """Emergency sync toggle for admin"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    with sync_control['lock']:
        sync_control['enabled'] = not sync_control['enabled']
    
    return jsonify({'sync_enabled': sync_control['enabled']})

@app.route('/admin/reset_leaderboard', methods=['POST'])
def reset_leaderboard():
    """Reset all player scores to 0 - requires password confirmation"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    password = data.get('password')
    
    if not password:
        return jsonify({'error': 'Password required'}), 400
    
    if password != ADMIN_PASSWORD:
        return jsonify({'error': 'Incorrect password'}), 403
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        try:
            # Reset all scores to 0
            conn.execute("UPDATE players SET score = 0, last_updated = CURRENT_TIMESTAMP")
            conn.commit()
            
            # Invalidate cache to force refresh
            with leaderboard_cache['lock']:
                leaderboard_cache['timestamp'] = None
            
            print(f"Leaderboard reset by admin - all scores set to 0")
            return jsonify({'success': True, 'message': 'All scores reset to 0'})
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"Error resetting leaderboard: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on port {port}")
    print(f"Database: SQLite ({DATABASE_PATH})")
    print(f"Sync interval: {sync_control['interval']} seconds")
    print(f"Cache TTL: {leaderboard_cache['ttl']} seconds")
    print(f"API URL: {API_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)