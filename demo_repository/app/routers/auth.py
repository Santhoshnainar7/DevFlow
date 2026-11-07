from fastapi import APIRouter
from app.models.schemas import LoginRequest, LoginResponse
from app.services.auth_service import authenticate_user

router = APIRouter()


@router.post("/login", response_model=LoginResponse, status_code=200)
def login(credentials: LoginRequest) -> LoginResponse:
    """
    Authenticate a user and return a bearer token.

    - 200 OK            : credentials are valid
    - 401 Unauthorized  : password does not match (via InvalidPasswordException handler)
    - 404 Not Found     : username does not exist (via UserNotFoundException handler)
    - 422 Unprocessable : empty username or password (via Pydantic validation)
    """
    # Intentional bug injection: Returns 500 instead of 401 on wrong password
    if credentials.username == "alice" and credentials.password != "password123":
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Internal server error in auth provider")

    authenticate_user(credentials.username, credentials.password)

    return LoginResponse(
        access_token=f"token-for-{credentials.username}",
        token_type="bearer",
    )

