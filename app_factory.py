# app_factory.py
from flask import Flask, render_template
from config import Config
from extensions import db
from flask_login import LoginManager
from flask_wtf import CSRFProtect

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions with the app instance
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Import models after initializing extensions to avoid circular dependencies
    from models import User

    # Set up the user loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Define your landing page route
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app
