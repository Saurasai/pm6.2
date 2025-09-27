import os
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, field_validator
import sqlite3
from dotenv import load_dotenv
import tweepy
import logging
import uuid
import requests
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import json

import os
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)


load_dotenv()
app = FastAPI(title="Post Muse", version="1.0.0")
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"])
DB_PATH = os.getenv("DB_PATH", "data/post_muse.db")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Platforms
PLATFORMS = ["bluesky", "facebook", "gmb", "instagram", "linkedin", "pinterest", "reddit", "snapchat", "telegram", "tiktok", "threads", "twitter", "youtube"]

# Instagram OAuth Config
INSTAGRAM_CLIENT_ID = os.getenv("INSTAGRAM_CLIENT_ID")
INSTAGRAM_CLIENT_SECRET = os.getenv("INSTAGRAM_CLIENT_SECRET")
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/auth/instagram/callback")

# Mock client for non-Twitter/Instagram
class MockClient:
    def post(self, content: str, platform: str, media_urls: Optional[List[str]] = None) -> Dict:
        return {"status": "success", "id": str(uuid.uuid4()), "postUrl": f"https://{platform}.com/post/{uuid.uuid4()}"}

mock_client = MockClient()

# Twitter Client
def get_twitter_client(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        logger.error(f"Non-admin user {user_id} attempted to access Twitter client")
        raise HTTPException(403, "Twitter posting restricted to admin users")
    return tweepy.Client(
        consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
        consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    )

# DB Init
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            api_key TEXT UNIQUE,
            tier TEXT DEFAULT 'free',
            api_calls INTEGER DEFAULT 0,
            monthly_posts INTEGER DEFAULT 0,
            is_admin BOOLEAN DEFAULT FALSE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            content TEXT,
            platforms TEXT,
            status TEXT DEFAULT 'pending',
            post_ids TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS platform_tokens (
            user_id TEXT,
            platform TEXT,
            access_token TEXT,
            refresh_token TEXT,
            expiry INTEGER,
            PRIMARY KEY (user_id, platform)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            content TEXT,
            platform TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Models
import os
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from dotenv import load_dotenv

# ✅ Load environment variables from .env
load_dotenv()

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str
    admin_secret: Optional[str] = None  # Comes from user input
    is_admin: bool = False
    tier: str = "free"

    @field_validator("confirm_password")
    def passwords_match(cls, v, info):
        if info.data.get("password") and v != info.data.get("password"):
            raise ValueError("Passwords do not match")
        return v

    @field_validator("is_admin")
    def restrict_admin(cls, v, info):
        if v and info.data.get("admin_secret") != os.getenv("ADMIN_SECRET"):
            raise ValueError("Invalid admin secret")
        return v



class PostRequest(BaseModel):
    post: str
    platforms: List[str]
    mediaUrls: Optional[List[str]] = None
    shortUrl: Optional[bool] = False
    autoHashtag: Optional[bool] = False
    autoSchedule: Optional[bool] = False
    mentions: Optional[List[str]] = None
    notes: Optional[str] = None
    requiresApproval: Optional[bool] = False
    evergreen: Optional[Dict[str, int]] = None

class PostResponse(BaseModel):
    status: str
    id: str
    postIds: List[Dict[str, str]]

class DraftRequest(BaseModel):
    content: str
    platform: str

class LoginRequest(BaseModel):
    email: str
    password: str

# Token Encryption
def encrypt_token(token: str) -> str:
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    return cipher.decrypt(encrypted.encode()).decode()

# Auth Dependency
def get_current_user(authorization: str = Depends(security)) -> str:
    try:
        token = authorization.credentials
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, tier, monthly_posts, is_admin FROM users WHERE api_key = ?", (token,))
        row = c.fetchone()
        conn.close()
        if not row:
            logger.error(f"Invalid API key: {token[:4]}... (truncated)")
            raise HTTPException(401, "Invalid API key")
        user_id, tier, monthly_posts, is_admin = row
        if tier == "free" and monthly_posts >= 20:
            logger.warning(f"Free tier limit reached for user_id: {user_id}")
            raise HTTPException(429, "Free tier limit reached")
        logger.debug(f"Authenticated user_id: {user_id}, tier: {tier}, is_admin: {is_admin}")
        return user_id
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        raise HTTPException(401, "Invalid API key")

# Login Endpoint
@app.post("/api/login")
async def login_user(request: LoginRequest):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT password, api_key FROM users WHERE email = ?", (request.email.lower(),))
        row = c.fetchone()
        conn.close()
        if row and pwd_context.verify(request.password, row[0]):
            logger.debug(f"Login successful for {request.email}")
            return {"api_key": row[1], "message": "Login successful"}
        logger.warning(f"Invalid credentials for {request.email}")
        raise HTTPException(401, "Invalid email or password")
    except Exception as e:
        logger.error(f"Login error for {request.email}: {str(e)}")
        raise HTTPException(500, f"Login error: {str(e)}")

# Get Platform Token
def get_platform_token(user_id: str, platform: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT access_token, refresh_token, expiry FROM platform_tokens WHERE user_id = ? AND platform = ?", (user_id, platform))
    row = c.fetchone()
    conn.close()
    if row:
        return {"access_token": decrypt_token(row[0]), "refresh_token": row[1] and decrypt_token(row[1]), "expiry": row[2]}
    return None

# Instagram Posting (Mock)
def post_to_instagram(user_id: str, content: str, media_urls: Optional[List[str]] = None) -> Dict:
    token = get_platform_token(user_id, "instagram")
    if not token:
        return {"status": "error", "id": None, "error": "No Instagram token"}
    try:
        response = requests.post(
            f"https://graph.instagram.com/me/media",
            params={"access_token": token["access_token"], "caption": content, "image_url": media_urls[0] if media_urls else None}
        )
        response.raise_for_status()
        return {"status": "success", "id": response.json().get("id", str(uuid.uuid4())), "postUrl": f"https://instagram.com/p/{uuid.uuid4()}"}
    except Exception as e:
        return {"status": "error", "id": None, "error": str(e)}

# Post Endpoint
@app.post("/api/post", response_model=PostResponse)
async def create_post(request: PostRequest, user_id: str = Depends(get_current_user)):
    if not all(p in PLATFORMS for p in request.platforms):
        raise HTTPException(400, "Invalid platforms")
    
    # Check if user is admin for Twitter posting
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    is_admin = row[0] if row else False
    conn.close()
    
    if "twitter" in request.platforms and not is_admin:
        logger.error(f"Non-admin user {user_id} attempted to post to Twitter")
        raise HTTPException(403, "Twitter posting restricted to admin users")
    
    post_id = str(uuid.uuid4())
    status = "awaiting_approval" if request.requiresApproval else "success"
    
    post_ids = []
    for platform in request.platforms:
        if platform == "twitter":
            try:
                client = get_twitter_client(user_id)  # This already checks for admin
                response = client.create_tweet(text=request.post)
                post_ids.append({"platform": platform, "status": "success", "id": str(response.data['id']), "postUrl": f"https://twitter.com/user/status/{response.data['id']}"})
            except Exception as e:
                post_ids.append({"platform": platform, "status": "error", "id": None, "error": str(e)})
        elif platform == "instagram":
            result = post_to_instagram(user_id, request.post, request.mediaUrls)
            post_ids.append({"platform": platform, **result})
        else:
            mock_id = mock_client.post(request.post, platform, request.mediaUrls)
            post_ids.append({"platform": platform, **mock_id})
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO posts (id, user_id, content, platforms, status, post_ids, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (post_id, user_id, request.post, str(request.platforms), status, str(post_ids), datetime.utcnow().isoformat()))
    c.execute("UPDATE users SET monthly_posts = monthly_posts + 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return PostResponse(status=status, id=post_id, postIds=post_ids)

# Draft Endpoint
@app.post("/api/draft")
async def save_draft(request: DraftRequest, user_id: str = Depends(get_current_user)):
    draft_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO drafts (id, user_id, content, platform, created_at) VALUES (?, ?, ?, ?, ?)",
              (draft_id, user_id, request.content, request.platform, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    logger.info(f"Draft saved for user {user_id} on platform {request.platform}")
    return {"status": "success", "id": draft_id}

# Get Drafts Endpoint
@app.get("/api/drafts")
async def get_drafts(user_id: str = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content, platform, created_at FROM drafts WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    drafts = c.fetchall()
    conn.close()
    return [{"id": d[0], "content": d[1], "platform": d[2], "created_at": d[3]} for d in drafts]

# Delete Endpoint
@app.delete("/api/post/{post_id}")
async def delete_post(post_id: str, user_id: str = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT post_ids FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        return {"status": "deleted"}
    conn.close()
    raise HTTPException(404, "Post not found")

# User Management
@app.post("/api/user")
async def create_user(request: UserCreateRequest):
    hashed = pwd_context.hash(request.password)
    api_key = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (id, email, password, api_key, tier, is_admin) VALUES (?, ?, ?, ?, ?, ?)", 
                  (str(uuid.uuid4()), request.email.lower(), hashed, api_key, request.tier, request.is_admin))
        conn.commit()
        logger.info(f"User created: {request.email}, is_admin: {request.is_admin}")
        return {"api_key": api_key}
    except sqlite3.IntegrityError:
        logger.warning(f"User creation failed: {request.email} already exists")
        raise HTTPException(400, "User exists")
    finally:
        conn.close()

# Get User Info
@app.get("/api/user")
async def get_user(user_id: str = Depends(get_current_user)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT email, tier, is_admin FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"email": row[0], "tier": row[1], "is_admin": bool(row[2])}
    raise HTTPException(404, "User not found")