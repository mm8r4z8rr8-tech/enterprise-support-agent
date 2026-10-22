
import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import get_db
from app.routers import tickets, users


app = FastAPI(
    title="Enterprise Support Agent",
    description="企业智能客服与工单管理系统",
    version="0.1.0",
)

# 配置基础日志格式和日志级别
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)

# 创建当前模块的日志记录器
logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    # 在服务端记录完整异常堆栈，方便排查问题
    logger.exception(
        "Unhandled exception: %s %s",
        request.method,
        request.url.path,
    )

    # 返回给客户端的内容不包含内部异常细节
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/db-health")
def database_health_check(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "connected"}


app.include_router(tickets.router)
app.include_router(users.router)
