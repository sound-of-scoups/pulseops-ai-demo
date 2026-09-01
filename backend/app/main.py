# backend/app/main.py
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.agents import router as agents_router

# 初始化全栈高性能微服务总网关
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FDE 智能产品工程 - 高级产品经理技术全能力演练项目后端控制台 (2026 生产级)",
    version="1.0.0"
)

# =====================================================================
# 全栈跨域（CORS）宽容解耦安全防御策略
# =====================================================================
# 允许 Vue 3 前端开发服务器（常见端口 5173、3000）以及大厂灰度内部网关进行跨域请求
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许 REST (GET/POST) 与长连接 OPTIONS 预检请求
    allow_headers=["*"],  # 允许 SSE 通信携带的特异化 Headers
)

# =====================================================================
# 路由层挂载
# =====================================================================
# 将多智能体协同矩阵与 SSE 编排流分发路由注册到根路径
app.include_router(agents_router)

@app.get("/health")
async def health_check():
    """微服务健康度检查检查哨（接入大厂 Kubernetes / Consul 灰度探针）"""
    return {
        "status": "UP",
        "framework": "FastAPI + Agno (2026 Edition)",
        "project": settings.PROJECT_NAME
    }

# Keep API routes above this catch-all mount. When deployed, the Vue build is
# copied here so the complete demo is served from one public URL.
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    @app.get("/", include_in_schema=False)
    async def frontend_entry():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")

if __name__ == "__main__":
    # 大厂单机研发调试环境的高性能单进程工作模式配置
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
