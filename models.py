# models.py
from flask_login import UserMixin
from extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # NEVER store plaintext passwords in production!
    password = db.Column(db.String(128), nullable=False)
    # New field for storing the filename (or path) of the uploaded profile picture
    profile_picture = db.Column(db.String(256), nullable=True)
    # New field for user roles: 'user', 'admin', or 'mod'
    role = db.Column(db.String(20), nullable=False, default='user')

    def __repr__(self):
        return f'<User {self.username}>'

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic details
    title = db.Column(db.String(255), nullable=False)      # e.g., "Ranma 1/2"
    rating = db.Column(db.String(20))                        # e.g., "PG-13"
    quality = db.Column(db.String(10))                       # e.g., "HD"
    
    # Count field
    episode_count = db.Column(db.Integer)                    # e.g., 12
    
    # Broadcast information
    type = db.Column(db.String(50))                          # e.g., "TV"
    duration = db.Column(db.String(20))                      # e.g., "23m"
    
    # Descriptive text
    description = db.Column(db.Text)                         # Long description text
    japanese_title = db.Column(db.String(255))               # e.g., "らんま1/2"
    synonyms = db.Column(db.String(255))                     # e.g., "Ranma 1/2, Ranma ½ Nettou Hen"
    
    # Airing and status
    aired = db.Column(db.String(255))                        # e.g., "Oct 6, 2024 to Dec 22, 2024"
    premiered = db.Column(db.String(50))                     # e.g., "Fall 2024"
    status = db.Column(db.String(50))                        # e.g., "Finished Airing"
    mal_score = db.Column(db.Float)                          # e.g., 8.13
    
    # Additional details
    genres = db.Column(db.String(255))                       # e.g., "Action, Comedy, Ecchi, Romance"
    studios = db.Column(db.String(255))                      # e.g., "MAPPA"
    producers = db.Column(db.String(255))                    # e.g., "dugout, Shogakukan-Shueisha Productions"
    
    # Images
    poster_image = db.Column(db.String(255))                 # Poster image URL or file path
    portrait_image = db.Column(db.String(255))               # Additional portrait image URL or file path
    
    def __repr__(self):
        return f"<Anime {self.title}>"
