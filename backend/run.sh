#!/bin/bash

# backend/run.sh
# 遇到非零返回值直接退出，打印错误行号
set -e

echo "====================================================================="
echo "🚀 [FDE Engine] 正在拉起大厂级多智能体协同矩阵后端网关..."
echo "====================================================================="

# 1. 动态锚定当前脚本所在的物理绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 2. 强制锁定并注入 Python 环境变量骨干网络，彻底解决相对路径导入死锁
export PYTHONPATH="$SCRIPT_DIR"
echo "🔍 [Environment] PYTHONPATH 已成功锚定为: $PYTHONPATH"


# 4. 灰度测试安全防护端口占用清理
echo "🛡️ [Port Check] 正在检查 8000 端口占用情况..."
if lsof -i:8000 >/dev/null 2>&1; then
    echo "⚠️ [Port Alert] 8000 端口已被占用，正在进行灰度优雅平替清理..."
    lsof -ti:8000 | xargs kill -9 || true
    sleep 1
fi

# 5. 正式自举拉起高性能 ASGI 服务器
echo "🔥 [Engine Launch] 正在拉起 Uvicorn 服务网关 (127.0.0.1:8000) (Reload 模式已开启)..."
echo "---------------------------------------------------------------------"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload