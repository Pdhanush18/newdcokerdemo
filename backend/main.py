"""
ExDock Backend - FastAPI + MongoDB Authentication Service
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, field_validator
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ExDock Auth API",
    description="Authentication service for ExDock platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Config ───────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# ─── DB ───────────────────────────────────────────────────────────────────────
client = MongoClient(MONGO_URI)
db = client["exdock"]
users_col = db["users"]

# Ensure unique email index
users_col.create_index("email", unique=True)

# ─── Security ─────────────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer()


# ─── Pydantic Models ──────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    created_at: str


# ─── Helpers ──────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    # Truncate to 72 bytes to comply with bcrypt limits
    pwd_bytes = plain.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = users_col.find_one({"email": email})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "ExDock Auth API is running"}


@app.post("/auth/signup", response_model=TokenResponse, status_code=201, tags=["Auth"])
def signup(body: SignupRequest):
    """Register a new user account."""
    hashed = hash_password(body.password)
    user_doc = {
        "name": body.name,
        "email": body.email,
        "hashed_password": hashed,
        "created_at": datetime.utcnow().isoformat(),
    }
    try:
        result = users_col.insert_one(user_doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    token = create_access_token(
        {"sub": body.email},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        user={"id": str(result.inserted_id), "name": body.name, "email": body.email},
    )


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(body: LoginRequest):
    """Authenticate with email and password."""
    user = users_col.find_one({"email": body.email})
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(
        {"sub": user["email"]},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        user={
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
        },
    )


@app.get("/auth/me", response_model=UserProfile, tags=["Auth"])
def get_me(current_user: dict = Depends(get_current_user)):
    """Get the authenticated user's profile."""
    return UserProfile(
        id=str(current_user["_id"]),
        name=current_user["name"],
        email=current_user["email"],
        created_at=current_user.get("created_at", ""),
    )