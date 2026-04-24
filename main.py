from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import base64
import binascii
import secrets

from config.settings import settings
from models.database import init_db

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_logger")

# 初始化数据库
init_db()

app = FastAPI(title=settings.app_name, debug=settings.debug)

from starlette.concurrency import iterate_in_threadpool


AUTH_EXEMPT_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
}


def _is_auth_exempt_path(path: str) -> bool:
    if path in AUTH_EXEMPT_PATHS:
        return True
    return path.startswith("/docs/") or path.startswith("/redoc/")


def _parse_basic_auth(authorization: str):
    if not authorization or not authorization.startswith("Basic "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    return decoded.split(":", 1)


def _is_authorized(request: Request) -> bool:
    creds = _parse_basic_auth(request.headers.get("Authorization", ""))
    if not creds:
        return False
    username, password = creds
    return secrets.compare_digest(
        username, settings.auth_username
    ) and secrets.compare_digest(password, settings.auth_password)


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if not settings.auth_enabled or _is_auth_exempt_path(request.url.path):
        return await call_next(request)

    if _is_authorized(request):
        return await call_next(request)

    return JSONResponse(
        status_code=401,
        content={"detail": "未授权访问，请提供有效账号密码"},
        headers={"WWW-Authenticate": "Basic"},
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"➡️ Request: {request.method} {request.url}")

    response = await call_next(request)

    # 捕获响应体以便记录日志
    response_body = [chunk async for chunk in response.body_iterator]
    response.body_iterator = iterate_in_threadpool(iter(response_body))

    try:
        if response_body:
            body_content = response_body[0].decode()
            display_content = (
                body_content[:1000] + "..."
                if len(body_content) > 1000
                else body_content
            )
            logger.info(f"📄 Response Data: {display_content}")
    except Exception:
        logger.info("📄 Response Data: [无法解析的内容]")

    logger.info(f"⬅️ Response Status: {response.status_code}")
    return response


# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from api.upload import router as upload_router
from api.cases import router as cases_router
from api.clues import router as clues_router
from api.analyze import router as analyze_router
from api.relations import router as relations_router
from api.ledger import router as ledger_router
from api.export import router as export_router
from api.report import router as report_router

app.include_router(upload_router)
app.include_router(cases_router)
app.include_router(clues_router)
app.include_router(analyze_router)
app.include_router(relations_router)
app.include_router(ledger_router)
app.include_router(export_router)
app.include_router(report_router)


@app.get("/")
def root():
    return {"message": "火眼智擎—汽配领域知产保护分析助手", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
