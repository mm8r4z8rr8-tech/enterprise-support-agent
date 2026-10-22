
import os

import redis
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
load_dotenv()

# 读取 Redis 连接地址
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://127.0.0.1:6379/0",
)

# 创建 Redis 客户端
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
)
