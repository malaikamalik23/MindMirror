from datetime import timedelta
from dotenv import load_dotenv
import os

basedir = os.path.abspath(os.path.dirname(__file__))

# Load .env here, before the Config class reads environment variables.
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # Set SECRET_KEY in a .env file (see .env.example). The fallback is only
    # for local development and must never be used on a live site.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-insecure-key-change-me'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 🔐 Flask-Login Remember Me settings
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = False  # Set True if using HTTPS in production
    SESSION_PROTECTION = "strong"  # Optional, adds extra security
