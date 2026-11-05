from fastapi import FastAPI
from app.routers import auth
from app.core.exceptions import (
    UserNotFoundException,
    InvalidPasswordException,
    MissingCredentialsException,
    user_not_found_handler,
    invalid_password_handler,
    missing_credentials_handler,
)

app = FastAPI(
    title="DevFlow Sample Login API",
    description="A minimal FastAPI login service used to demonstrate DevFlow bug investigation.",
    version="1.0.0",
)

# Register routers
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])

# Register custom exception handlers
app.add_exception_handler(UserNotFoundException, user_not_found_handler)
app.add_exception_handler(InvalidPasswordException, invalid_password_handler)
app.add_exception_handler(MissingCredentialsException, missing_credentials_handler)

