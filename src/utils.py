 
# utils.py
import os
from dotenv import load_dotenv

def load_env_vars():
    """
    Loads essential configuration variables from environment variables.

    Attempts to load from a .env file first, then system environment.
    Requires: FLASK_SECRET_KEY, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    Optional: GOOGLE_API_KEY (can be provided via UI)

    Returns:
        dict: A dictionary containing the loaded configuration variables.
              google_api_key will be None if not found in the environment.

    Raises:
        ValueError: If any mandatory database or Flask variable is not defined.
    """
    load_dotenv()

    config = {
        "flask_secret_key": os.getenv("FLASK_SECRET_KEY"),
        "db_host": os.getenv("DB_HOST"),
        "db_port": os.getenv("DB_PORT"),
        "db_name": os.getenv("DB_NAME"),
        "db_user": os.getenv("DB_USER"),
        "db_password": os.getenv("DB_PASSWORD"),
        "google_api_key": os.getenv("GOOGLE_API_KEY") # Optional from env
    }

    # Validation for mandatory keys
    required_keys = [
        "flask_secret_key", "db_host", "db_port",
        "db_name", "db_user", "db_password"
    ]
    missing_keys = [key for key in required_keys if not config[key]]

    if missing_keys:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_keys)}")

    if not config["google_api_key"]:
        print("Info: GOOGLE_API_KEY not found in environment. Will rely on UI input if needed.")

    print("Database Configuration Loaded (partially hidden):")
    print(f"  DB Host: {config['db_host']}")
    print(f"  DB Port: {config['db_port']}")
    print(f"  DB Name: {config['db_name']}")
    print(f"  DB User: {config['db_user']}")
    print(f"  DB Password: {'*' * len(config['db_password']) if config['db_password'] else 'Not Set'}")
    print(f"  Google API Key from Env: {'Found' if config['google_api_key'] else 'Not Found'}")

    return config

# Load config when module is imported
try:
    APP_CONFIG = load_env_vars()
except ValueError as e:
    print(f"CRITICAL CONFIGURATION ERROR: {e}")
    # Set defaults or exit if running in a context where defaults are unacceptable
    APP_CONFIG = {
        "flask_secret_key": "default-insecure-key-change-me",
        # Add other defaults or None values if you want the app to try starting
    }
    print("WARNING: Using default/missing configuration due to error.")