from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = {"schema": None}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    pw_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=db.func.current_timestamp(),
    )

    def set_password(self, password: str) -> None:
        self.pw_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.pw_hash, password)
