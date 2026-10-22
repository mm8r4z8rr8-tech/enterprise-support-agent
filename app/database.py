import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 加载项目根目录下的 .env 文件
load_dotenv()

# 从环境变量读取数据库配置
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 检查必要配置是否存在，避免连接时才发现配置缺失
if not all([DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError("数据库配置缺失，请检查项目根目录下的 .env 文件")

# 拼接 SQLAlchemy 使用的 MySQL 连接地址
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# 创建数据库引擎，负责管理数据库连接
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # 使用连接前检查连接是否有效
    echo=True,           # 开发阶段打印 SQL，方便学习
)

# 创建数据库会话工厂
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# 所有 ORM 模型都继承这个基类
class Base(DeclarativeBase):
    pass


def get_db():
    # 创建一个数据库会话
    db = SessionLocal()

    try:
        # 将数据库会话提供给 FastAPI 接口
        yield db

    except Exception:
        # 请求处理过程中出现异常，回滚未提交的数据库操作
        db.rollback()

        # 继续抛出异常，让 FastAPI 正常处理
        raise

    finally:
        # 无论请求成功还是失败，都关闭数据库会话
        db.close()