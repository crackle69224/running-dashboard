import os

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

SECRET_KEY = os.environ["SECRET_KEY"]
SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
RESET_MAX_AGE = 60 * 60  # 1 hour

_serializer = URLSafeTimedSerializer(SECRET_KEY)
_reset_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="password-reset")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session_token(user_id: int) -> str:
    return _serializer.dumps({"user_id": user_id})


def verify_session_token(token: str) -> int | None:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data["user_id"]
    except (BadSignature, SignatureExpired):
        return None


def create_reset_token(user_id: int, password_hash: str) -> str:
    # Embedding the password hash at creation time means the token stops
    # working the moment the password actually changes, so a link can't be
    # replayed after its first successful use.
    return _reset_serializer.dumps({"user_id": user_id, "password_hash": password_hash})


def decode_reset_token(token: str) -> dict | None:
    try:
        return _reset_serializer.loads(token, max_age=RESET_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
