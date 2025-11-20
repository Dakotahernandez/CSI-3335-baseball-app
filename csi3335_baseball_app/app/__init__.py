import os
from typing import Optional

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from csi3335f2025 import mysql

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'change-me')

    user = mysql['user']
    password = mysql['password']
    host = mysql.get('host') or mysql.get('location') or 'localhost'
    database = mysql['database']
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{user}:{password}@{host}/{database}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    migrations_path = os.path.join(app.root_path, os.pardir, 'migrations')
    migrate.init_app(app, db, directory=migrations_path)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[User]:
        if not user_id:
            return None
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    from .auth import auth_bp
    from .routes import core_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(core_bp)

    return app
