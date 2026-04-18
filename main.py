from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

from config.settings import settings
from models.database import init_db

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api_logger")

# 初始化数据库
init_db()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug
)

from starlette.concurrency import iterate_in_threadpool

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
            display_content = body_content[:1000] + "..." if len(body_content) > 1000 else body_content
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

    uvicorn.run(app, host="0.0.0.0", port=8000)