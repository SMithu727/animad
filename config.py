# config.py
import os
from pathlib import Path

# Base directory
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # App secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email configuration
    MAIL_SERVER = 'smtp-relay.brevo.com'  # Your SMTP server
    MAIL_PORT = 587  # SMTP port (587 for TLS)
    MAIL_USE_TLS = True  # Use TLS for secure connection
    MAIL_USERNAME = '86ee34001@smtp-brevo.com'  # Your SMTP username
    MAIL_PASSWORD = 'jOMB2Yh91Nd0G3Eb'  # Your SMTP password
    MAIL_DEFAULT_SENDER = 'noreply@animad.site'  # Default sender email

    # Cache configuration
    CACHE_TYPE = 'SimpleCache'  # Use simple in-memory caching
    CACHE_DEFAULT_TIMEOUT = 86400  # Cache timeout in seconds (24 hours)

    # MyAnimeList (MAL) API configuration
    MAL_CLIENT_ID = '51e35dd154e9480cbe810f17a43240a8'  # Removed trailing space
    MAL_CLIENT_SECRET = 'f4fc075966ce8510d44824bb60086fa2f2cbda050c8e313ccbade4d1a42b1d91'
    MAL_REDIRECT_URI = 'http://animad.site/mal_callback'

    # File upload configuration
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')  # Path for file uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit

    # Google Cloud Translation API credentials
    GOOGLE_TRANSLATE_CREDENTIALS = os.path.join(basedir, 'credentials', 'innate-sunset-451719-c5-08a2d0e73f47.json')

    # Logging configuration
    LOG_LEVEL = 'DEBUG'  # Set to 'INFO' or 'WARNING' in production
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'