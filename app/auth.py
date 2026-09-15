"""Small dependency-free password and JWT helpers for the local trainer."""
import base64, hashlib, hmac, json, os, time
from fastapi import HTTPException, Request
from app.config import required_secret

SECRET = required_secret("JWT_SECRET")

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return "pbkdf2$120000$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        _, iterations, salt, digest = encoded.split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(base64.urlsafe_b64encode(actual).decode(), digest)
    except (ValueError, TypeError):
        return False

def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

def create_token(payload: dict, ttl_seconds: int = 8 * 3600) -> str:
    header = _b64(json.dumps({"alg":"HS256", "typ":"JWT"}, separators=(",", ":")).encode())
    body = dict(payload, exp=int(time.time()) + ttl_seconds)
    encoded = header + "." + _b64(json.dumps(body, separators=(",", ":")).encode())
    return encoded + "." + _b64(hmac.new(SECRET.encode(), encoded.encode(), hashlib.sha256).digest())

def decode_token(token: str) -> dict:
    try:
        header, body, signature = token.split(".")
        expected = _b64(hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected): raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(data.get("exp", 0)) < int(time.time()): raise ValueError()
        return data
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

def current_user(request: Request) -> dict:
    value = request.headers.get("Authorization", "")
    if not value.startswith("Bearer "): raise HTTPException(status_code=401, detail="Bearer token required")
    return decode_token(value[7:])

def optional_user(request: Request) -> dict | None:
    """Return claims when supplied; preserve anonymous demo-mode compatibility."""
    value = request.headers.get("Authorization", "")
    return decode_token(value[7:]) if value.startswith("Bearer ") else None

def require_role(*roles):
    def dependency(request: Request):
        user = current_user(request)
        if user.get("role") not in roles: raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dependency
