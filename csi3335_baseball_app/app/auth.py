from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from . import db
from .forms import LoginForm, RegisterForm
from .models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        existing_username = db.session.execute(select(User).filter_by(username=username)).scalar_one_or_none()
        existing_email = db.session.execute(select(User).filter_by(email=email)).scalar_one_or_none()

        if existing_username:
            flash('Username already registered. Choose another.', 'danger')
            return render_template('register.html', form=form)
        if existing_email:
            flash('Email already registered. Try logging in.', 'danger')
            return render_template('register.html', form=form)

        user = User(username=username, email=email)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Registration successful. Welcome!', 'success')
        return redirect(url_for('core.index'))

    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('core.index'))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = db.session.execute(select(User).filter_by(username=username)).scalar_one_or_none()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', form=form)

        login_user(user, remember=form.remember.data)
        flash('Logged in successfully.', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('core.index'))

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('core.index'))
