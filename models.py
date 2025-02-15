# models.py
from flask_login import UserMixin
from extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    profile_picture = db.Column(db.String(256), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='user')

    def __repr__(self):
        return f'<User {self.username}>'

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Add the MAL code so we can link JSON episodes to this anime
    mal_code = db.Column(db.String(20), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    rating = db.Column(db.String(20))
    quality = db.Column(db.String(10))
    episode_count = db.Column(db.Integer)
    type = db.Column(db.String(50))
    duration = db.Column(db.String(20))
    description = db.Column(db.Text)
    japanese_title = db.Column(db.String(255))
    synonyms = db.Column(db.String(255))
    aired = db.Column(db.String(255))
    premiered = db.Column(db.String(50))
    status = db.Column(db.String(50))
    mal_score = db.Column(db.Float)
    genres = db.Column(db.String(255))
    studios = db.Column(db.String(255))
    producers = db.Column(db.String(255))
    poster_image = db.Column(db.String(255))
    portrait_image = db.Column(db.String(255))

    # Relationship to episodes
    episodes = db.relationship('Episode', backref='anime', lazy=True)

    def __repr__(self):
        return f"<Anime {self.title}>"

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anime_id = db.Column(db.Integer, db.ForeignKey('anime.id'), nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    episode_url = db.Column(db.String(255))

    # Relationship to embed sources
    embeds = db.relationship('EpisodeEmbed', backref='episode', lazy=True)

    def __repr__(self):
        return f"<Episode {self.episode_number} of Anime ID {self.anime_id}>"

class EpisodeEmbed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    episode_id = db.Column(db.Integer, db.ForeignKey('episode.id'), nullable=False)
    server = db.Column(db.String(64), nullable=False)
    link = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Embed {self.server} for Episode ID {self.episode_id}>"
