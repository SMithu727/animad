# config.py
import os

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