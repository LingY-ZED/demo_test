"""
鉴权API路由 — JWT Bearer Token 登录
"""
import time
import uuid
import secrets

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config.settings import settings

router = APIRouter(prefix="/api/auth", tags=["鉴权"])


class LoginRequest(BaseModel):
    username: str
    password: str


def _get_secret_key() -> str:
    """获取 JWT 密钥，未配置则基于 app secret 生成稳定密钥"""
    if settings.jwt_secret_key:
        return settings.jwt_secret_key
    # 无显式配置时，用 auth_password 的派生值作为默认密钥，保证重启不失效
    return f"huoyan-jwt-{settings.auth_password}"


def create_access_token(username: str) -> str:
    """签发 JWT access token"""
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + settings.jwt_expire_minutes * 60,
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """解码并验证 JWT，成功返回 payload，失败返回 None"""
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        if payload.get("type") != "access":
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


@router.post("/login")
async def login(req: LoginRequest):
    """
    用户名密码登录，返回 JWT Bearer token

    成功响应: { access_token, token_type, expires_in }
    """
    if not secrets.compare_digest(req.username, settings.auth_username) or \
       not secrets.compare_digest(req.password, settings.auth_password):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    token = create_access_token(req.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
    }


@router.get("/status")
async def token_status(request: Request):
    """
    返回当前 token 的用户信息和剩余有效期
    需要有效的 Bearer token（由中间件校验）
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    now = int(time.time())
    return {
        "username": payload["sub"],
        "expires_at": payload["exp"],
        "remaining_seconds": max(0, payload["exp"] - now),
    }
