"""
auth.py — Authentication: password hashing, JWT tokens, user management.

Three responsibilities:
    1. Hash and verify passwords (bcrypt via passlib)
    2. Create and decode JWT tokens (python-jose)
    3. FastAPI dependency that protects routes (get_current_user)

Passwords are NEVER stored in plaintext — only bcrypt hashes.
Tokens are stateless: the server verifies the signature without hitting the DB.
"""

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from database import users_collection

load_dotenv()

# ---------------------------------------------------------------------------
# Config — loaded from .env
# ---------------------------------------------------------------------------
SECRET_KEY                  = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM                   = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# ---------------------------------------------------------------------------
# Password hashing
# CryptContext wraps bcrypt and handles the slow hashing automatically.
# bcrypt's "deprecated=auto" means it upgrades old hashes on next login.
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# OAuth2 scheme
# This tells FastAPI to look for a Bearer token in the Authorization header.
# The tokenUrl points to our /auth/login endpoint.
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plaintext password. Never store the plain version."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against its stored hash."""
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(email: str) -> str:
    """
    Create a signed JWT containing the user's email and an expiry time.
    The token is self-contained — the server doesn't need to look anything
    up to verify it, just check the signature with SECRET_KEY.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """
    Decode and verify a JWT. Returns the email (subject) if valid.
    Raises HTTPException 401 if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired. Please log in again.",
        )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

async def register_user(email: str, password: str) -> dict:
    """
    Create a new user. Raises 400 if email is already registered.
    Returns the new user document (without the password hash).
    """
    existing = await users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    user_doc = {
        "email":           email,
        "hashed_password": hash_password(password),
        "created_at":      str(datetime.now(timezone.utc)),
    }
    await users_collection.insert_one(user_doc)
    return {"email": email, "message": "Account created successfully."}


async def login_user(email: str, password: str) -> dict:
    """
    Verify credentials and return a JWT access token.
    Raises 401 if email not found or password is wrong.
    We return the same error for both cases — never tell an attacker
    which one failed (that would let them enumerate valid emails).
    """
    user = await users_collection.find_one({"email": email})
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(email)
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# FastAPI dependency — attach to any route that requires authentication
# ---------------------------------------------------------------------------

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency: reads the Bearer token from the Authorization header,
    verifies it, and returns the user's email.

    Usage in a route:
        @router.get("/protected")
        async def protected(user_email: str = Depends(get_current_user)):
            ...

    FastAPI calls this automatically before the route handler.
    Returns HTTP 401 if the token is missing, invalid, or expired.
    """
    return decode_token(token)
