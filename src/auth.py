import hashlib
import hmac
import json
import os
import secrets
from typing import Any

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


TOKEN_MAX_AGE_SECONDS = 1800
PASSWORD_ITERATIONS = 310000
TOKEN_SALT = "pulseiq-api-auth-v1"
ALLOWED_ROLES = {"ADMIN", "EXECUTIVE", "HR", "MANAGER"}

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")

    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_value),
        PASSWORD_ITERATIONS,
    ).hex()

    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt_value}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations_text)
        salt_bytes = bytes.fromhex(salt)

        if not 100_000 <= iterations <= 1_000_000:
            return False

        if len(salt_bytes) < 16 or len(expected) != 64:
            return False

        expected_bytes = bytes.fromhex(expected)
        if len(expected_bytes) != 32:
            return False

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt_bytes,
            iterations,
        )

        return hmac.compare_digest(actual, expected_bytes)

    except (ValueError, TypeError, AttributeError):
        return False
def get_auth_config() -> tuple[dict[str, Any], URLSafeTimedSerializer]:
    raw_users = os.getenv("PULSEIQ_AUTH_USERS")
    secret = os.getenv("PULSEIQ_TOKEN_SECRET")

    if not raw_users or not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured securely.",
        )

    try:
        users = json.loads(raw_users)
        if not isinstance(users, dict) or not users:
            raise ValueError("User configuration must be a non-empty object.")

        for username, details in users.items():
            if (
                not isinstance(username, str)
                or not isinstance(details, dict)
                or not isinstance(details.get("password_hash"), str)
                or details.get("role") not in ALLOWED_ROLES
            ):
                raise ValueError("Invalid user configuration.")

    except (json.JSONDecodeError, ValueError, TypeError):
        raise HTTPException(
            status_code=503,
            detail="Authentication user configuration is invalid.",
        )

    serializer = URLSafeTimedSerializer(secret, salt=TOKEN_SALT)
    return users, serializer


def authenticate_user(username: str, password: str) -> dict[str, str]:
    users, _ = get_auth_config()
    user = users.get(username)

    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    return {"username": username, "role": user["role"]}


def create_access_token(user: dict[str, str]) -> str:
    _, serializer = get_auth_config()
    return serializer.dumps({
        "sub": user["username"],
        "role": user["role"],
    })


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, str]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    users, serializer = get_auth_config()

    try:
        payload = serializer.loads(
            credentials.credentials,
            max_age=TOKEN_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid token.")

    username = payload.get("sub") if isinstance(payload, dict) else None
    role = payload.get("role") if isinstance(payload, dict) else None
    configured_user = users.get(username) if isinstance(username, str) else None

    if (
        not configured_user
        or configured_user.get("role") != role
        or role not in ALLOWED_ROLES
    ):
        raise HTTPException(status_code=401, detail="User or token permissions are invalid.")

    return {"username": username, "role": role}


def require_roles(*allowed_roles: str):
    def dependency(
        current_user: dict[str, str] = Security(get_current_user),
    ) -> dict[str, str]:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role permissions.")
        return current_user

    return dependency
