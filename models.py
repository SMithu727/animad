# models.py
from datetime import datetime
from flask_login import UserMixin
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # Change from 'password' to 'password_hash'
    profile_picture = db.Column(db.String(256), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='user', lazy=True)
    watch_history = db.relationship('WatchHistory', backref='user', lazy=True)

    # Password hashing
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

    def __repr__(self):
        return f'<User {self.username}>'

class Anime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    rating = db.Column(db.String(20))
    rating_ar = db.Column(db.String(50), nullable=True)
    quality = db.Column(db.String(10))
    episode_count = db.Column(db.Integer)
    type = db.Column(db.String(50))
    type_ar = db.Column(db.String(50), nullable=True)
    duration = db.Column(db.String(20))
    duration_ar = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text)
    description_ar = db.Column(db.Text, nullable=True)
    japanese_title = db.Column(db.String(255))
    synonyms = db.Column(db.String(255))
    aired = db.Column(db.String(255))
    aired_ar = db.Column(db.String(255), nullable=True)
    premiered = db.Column(db.String(50))
    premiered_ar = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50))
    status_ar = db.Column(db.String(50), nullable=True)
    mal_score = db.Column(db.Float)
    genres = db.Column(db.String(255))
    genres_ar = db.Column(db.String(255), nullable=True)
    studios = db.Column(db.String(255))
    producers = db.Column(db.String(255))
    poster_image = db.Column(db.String(255))
    portrait_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    episodes = db.relationship('Episode', backref='anime', lazy=True)
    comments = db.relationship('Comment', backref='anime', lazy=True)

    def __repr__(self):
        return f"<Anime {self.title}>"

class Episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anime_id = db.Column(db.Integer, db.ForeignKey('anime.id'), nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    episode_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anime_id = db.Column(db.Integer, db.ForeignKey('anime.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    dislikes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_flagged = db.Column(db.Boolean, default=False)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)

    def __repr__(self):
        return f"<Comment {self.id} by User {self.user_id} on Anime {self.anime_id}>"

class WatchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anime_id = db.Column(db.Integer, db.ForeignKey('anime.id'), nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    anime = db.relationship('Anime', backref='watch_histories', lazy=True)  # Add this relationship

    def __repr__(self):
        return f"<WatchHistory {self.anime.title} - Episode {self.episode_number}>"


class CommentVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    vote = db.Column(db.Integer, nullable=False)  # 1 for like, -1 for dislike

    __table_args__ = (db.UniqueConstraint('user_id', 'comment_id', name='_user_comment_uc'),)