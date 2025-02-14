from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from forms import LoginForm, SignupForm
from models import User, Anime

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    anime = Anime.query.first()
    top_anime = [anime] * 5  # placeholder
    return render_template('index.html', new_anime=anime, top_anime=top_anime)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.password == form.password.data:
            login_user(user)
            flash("Logged in successfully!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash("Invalid email or password.", "danger")
    return render_template('login.html', form=form)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # Place your user creation logic here
        flash("Account created successfully!", "success")
        return redirect(url_for('main.index'))
    return render_template('signup.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('main.index'))
