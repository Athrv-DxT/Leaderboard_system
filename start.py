#!/usr/bin/env python3
"""
Startup script for FunFinity Leaderboard
This ensures proper initialization and error handling
"""

import os
import sys
import time

def main():
    print("🚀 Starting FunFinity Leaderboard...")
    
    # Set environment variables if not set
    if not os.environ.get('SECRET_KEY'):
        os.environ['SECRET_KEY'] = '499d40c5943dba125e65670bbf7d3a4bfaa350faa4f313050b968ebc5f8688f8'
    
    try:
        # Import and run the Flask app
        from app import app
        
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        print(f"✅ Flask app initialized successfully")
        print(f"🌐 Starting server on {host}:{port}")
        print(f"📊 Background sync enabled")
        print(f"🔗 Public leaderboard: http://{host}:{port}/")
        print(f"🔑 Admin login: http://{host}:{port}/login")
        
        # Start the Flask app
        app.run(host=host, port=port, debug=False)
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
