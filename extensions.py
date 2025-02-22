# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache  # Import the Cache class

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()  # Initialize the cache object