from app.core.exceptions import InvalidPasswordException, UserNotFoundException

# ---------------------------------------------------------------------------
# In-memory user store — intentionally plain-text for demo purposes.
# Real apps must hash passwords (e.g. bcrypt).
# ---------------------------------------------------------------------------
_USER_STORE: dict[str, str] = {
    "alice": "password123",
    "bob": "securepass",
    "admin": "admin2024",
}


def authenticate_user(username: str, password: str) -> dict:
    """
    Validate credentials against the in-memory store.

    Returns the user record on success.
    Raises UserNotFoundException if the username does not exist.
    Raises InvalidPasswordException if the password does not match.
    """
    if username not in _USER_STORE:
        raise UserNotFoundException(username)

    if _USER_STORE[username] != password:
        raise InvalidPasswordException(username)

    return {"username": username}

