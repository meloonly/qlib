# 自动化交易系统 Docker镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p logs reports backups data

# 设置权限
RUN chmod +x run_trading_system.py scheduler.py web_dashboard.py

# 暴露端口 (Web仪表盘)
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '.'); from config_manager import ConfigManager; ConfigManager()" || exit 1

# 默认启动命令（交互式菜单）
CMD ["python", "run_trading_system.py", "--menu"]
