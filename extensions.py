# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from flask_mail import Mail  # Import Flask-Mail
from flask_wtf.csrf import CSRFProtect  # Import CSRFProtect

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
mail = Mail()  # Initialize Flask-Mail
csrf = CSRFProtect()  # Initialize CSRFProtect