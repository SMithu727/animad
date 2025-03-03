# app_factory.py
from flask import Flask
from config import Config
from extensions import db, migrate, cache, mail
from flask_login import LoginManager
from flask_wtf import CSRFProtect
import os
from errors import register_error_handlers  # Import error handlers

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    # Create the Flask app instance
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration from Config class
    app.config.from_object(Config)

    # Set UPLOAD_FOLDER configuration
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    mail.init_app(app)

    # Register error handlers **before** blueprints
    register_error_handlers(app)

    # Import models within app context
    with app.app_context():
        from models import User, Anime

    # Define user_loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprint
    from app import bp
    app.register_blueprint(bp)

    return app