#!/usr/bin/env python3
"""
Startup script for DolbyMusic on Heroku
This script ensures all necessary directories and permissions are set up
"""

import os
import sys

def setup_heroku_environment():
    """Set up environment for Heroku deployment"""
    
    print("🚀 Setting up DolbyMusic for Heroku...")
    
    # Create necessary directories
    directories = [
        "downloads",
        "logs",
        "cache"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created/verified directory: {directory}")
        except Exception as e:
            print(f"⚠️ Warning: Could not create directory {directory}: {e}")
    
    # Check critical files
    critical_files = [
        "Dolbymusic/__init__.py",
        "strings/langs/en.yml",
        "config.py"
    ]
    
    for file_path in critical_files:
        if os.path.exists(file_path):
            print(f"✅ Critical file found: {file_path}")
        else:
            print(f"❌ Critical file missing: {file_path}")
            return False
    
    # Check environment variables
    required_env_vars = [
        "API_ID",
        "API_HASH", 
        "BOT_TOKEN",
        "MONGO_DB_URI",
        "OWNER_ID"
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All required environment variables are set")
    
    # Set Python path
    current_dir = os.getcwd()
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        print(f"✅ Added {current_dir} to Python path")
    
    print("🎵 DolbyMusic setup complete! Starting bot...")
    return True

if __name__ == "__main__":
    if setup_heroku_environment():
        # Import and start the bot
        try:
            print("🎵 Starting DolbyMusic bot...")
            # Import the main module and run it
            import asyncio
            from Dolbymusic.__main__ import init
            
            # Run the bot's main function
            asyncio.get_event_loop().run_until_complete(init())
            
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        print("❌ Setup failed. Please check your configuration.")
        sys.exit(1)
