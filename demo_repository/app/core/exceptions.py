# sample_app/app/core/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse


class UserNotFoundException(Exception):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"User '{username}' not found.")


class InvalidPasswordException(Exception):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Invalid password for user '{username}'.")


class MissingCredentialsException(Exception):
    def __init__(self, field: str):
        self.field = field
        super().__init__(f"Missing required field: '{field}'.")


# ---------------------------------------------------------------------------
# FastAPI exception handlers — registered in main.py
# ---------------------------------------------------------------------------

async def user_not_found_handler(
    request: Request, exc: UserNotFoundException
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


async def invalid_password_handler(
    request: Request, exc: InvalidPasswordException
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
    )


async def missing_credentials_handler(
    request: Request, exc: MissingCredentialsException
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )

