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
    
    @app.cli.command("add-test-data")
    def add_test_data():
        from models import Anime
        test_anime = Anime(
            title="Ranma 1/2",
            rating="PG-13",
            quality="HD",
            episode_count=12,
            season_count=12,
            special_episode_count=12,
            type="TV",
            duration="23m",
            description="During their martial arts training expedition in China, Ranma Saotome and his father Genma suffered an accident, which in turn, afflicted them with a curse—whenever they are doused with cold water, Ranma transforms into a girl, while his father turns into a panda! Only hot water can reverse these changes, but any further contact with cold water opens the can of worms once more. Unfortunately, the trouble does not end there, as Ranma finds out about his betrothal to one of the daughters of Soun Tendou, his father's closest friend. During the families' first meeting, it is decided that Ranma is to be married to Akane, the youngest daughter, a decision that is met with vehement protests from both sides. The two are simply not compatible, yet they are forced to live under one roof. Ranma's status quo further adds to the chaos, leading him to a series of comedic situations and misunderstandings that, in the grand scheme of things, may just be what he needs to work with Akane. ",
            japanese_title="らんま1/2",
            synonyms="Ranma 1/2, Ranma ½ Nettou Hen",
            aired="Oct 6, 2024 to Dec 22, 2024",
            premiered="Fall 2024",
            status="Finished Airing",
            mal_score=8.13,
            genres="Action, Comedy, Ecchi, Romance",
            studios="MAPPA",
            producers="dugout, Shogakukan-Shueisha Productions",
            poster_image="/static/images/ranma_poster.jpg",
            portrait_image="/static/images/ranma_portrait.jpg"
        )
        db.session.add(test_anime)
        db.session.commit()
        print("Added test anime entry")
    
    return app
    
    return app