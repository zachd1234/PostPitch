import os

# Function to get environment variables with fallback to secret.py if available
def get_api_key(key_name):
    # First try to get from environment variables
    env_value = os.environ.get(key_name)
    if env_value:
        return env_value
        
    # If not in environment, try to import from secret.py as fallback
    try:
        import secret
        if hasattr(secret, key_name):
            return getattr(secret, key_name)
    except ImportError:
        pass
        
    # Return empty string if not found
    return ""

# API Keys
OPENAI_API_KEY = get_api_key("OPENAI_API_KEY")
APOLLO_API_KEY = get_api_key("APOLLO_API_KEY") 
HUNTER_API_KEY = get_api_key("HUNTER_API_KEY")
GOOGLE_API_KEY = get_api_key("GOOGLE_API_KEY")

# Firebase config
FIREBASE_API_KEY = get_api_key("FIREBASE_API_KEY")
FIREBASE_AUTH_DOMAIN = os.environ.get("FIREBASE_AUTH_DOMAIN", "blog-emailer-294e0.firebaseapp.com")
FIREBASE_DATABASE_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://blog-emailer-294e0-default-rtdb.firebaseio.com")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "blog-emailer-294e0")
FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET", "blog-emailer-294e0.appspot.com")
FIREBASE_MESSAGING_SENDER_ID = get_api_key("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_APP_ID = get_api_key("FIREBASE_APP_ID")
FIREBASE_MEASUREMENT_ID = get_api_key("FIREBASE_MEASUREMENT_ID") 