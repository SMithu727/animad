# app_factory.py
from flask import Flask
from config import Config
from extensions import db, migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect

login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Import models within app context
    with app.app_context():
        from models import User, Anime
    
    # Define user_loader here (critical for Flask-Login)
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Import and register the blueprint from app.py
    from app import bp
    app.register_blueprint(bp)
    
    return app