# Docker 部署指南

## 概述

本文档介绍如何使用 Docker 一键部署自动化交易系统到云端或本地服务器。

## 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB RAM
- 10GB 可用磁盘空间

## 快速开始

### 1. 一键启动

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 2. 访问服务

- **Web 仪表盘**: http://localhost:5000
- **API 端点**: http://localhost:5000/api/

### 3. 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（谨慎使用）
docker-compose down -v
```

## 服务架构

系统包含两个 Docker 服务：

### trading-system (主交易服务)
- **功能**: 运行自动化调度器，执行定时交易任务
- **启动命令**: `python scheduler.py start`
- **定时任务**:
  - 09:30 - 数据更新
  - 16:00 - 每日信号检测
  - 每周日备份
  - 每小时健康检查

### web-dashboard (Web 仪表盘)
- **功能**: 提供 Web 界面监控系统状态
- **端口**: 5000
- **API 端点**:
  - `/api/system_status` - 系统状态
  - `/api/portfolio` - 组合信息
  - `/api/signals/<stock_code>` - 交易信号
  - `/api/performance` - 性能指标

## 配置文件

### 必要配置文件

在启动前，请确保以下配置文件已准备好：

1. **system_config.yaml** - 系统配置
```yaml
# 示例配置
trading:
  market: "CN"  # CN/HK/US
  initial_capital: 1000000
  max_position_size: 0.1
  stop_loss: 0.05
  take_profit: 0.15

data_sources:
  primary: "tushare"  # tushare/yfinance
  tushare_token: "YOUR_TOKEN"

notifications:
  enabled: true
  email: "your@email.com"
```

2. **email_config.json** - 邮件通知配置
```json
{
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "username": "your@email.com",
  "password": "your_app_password",
  "recipients": ["alert@email.com"]
}
```

### 数据持久化

以下目录/文件会自动持久化到主机：

- `./data/` - 市场数据缓存
- `./logs/` - 系统日志
- `./reports/` - 交易报告和分析
- `./backups/` - 数据备份
- `./portfolio.db` - 组合数据库
- `./strategy_performance.json` - 策略表现记录

## 环境变量

可通过环境变量自定义配置：

```yaml
environment:
  - TZ=Asia/Shanghai          # 时区
  - PYTHONUNBUFFERED=1        # 实时日志输出
  - FLASK_ENV=production      # Flask 环境
```

## 云端部署

### AWS EC2 部署

```bash
# 1. 连接到 EC2 实例
ssh -i your-key.pem ec2-user@your-instance-ip

# 2. 安装 Docker
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -a -G docker ec2-user

# 3. 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. 上传项目文件
scp -i your-key.pem -r ./auto_trading ec2-user@your-instance-ip:~/

# 5. 启动服务
cd ~/auto_trading
docker-compose up -d --build
```

### 阿里云 ECS 部署

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo systemctl start docker
sudo systemctl enable docker

# 2. 安装 Docker Compose
sudo pip3 install docker-compose

# 3. 配置阿里云镜像加速
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": ["https://your-mirror.mirror.aliyuncs.com"]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker

# 4. 部署
docker-compose up -d --build
```

### 腾讯云 CVM 部署

```bash
# 类似 AWS EC2 步骤
# 注意：使用腾讯云容器镜像服务加速
```

## 监控与维护

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 仅查看交易系统日志
docker-compose logs -f trading-system

# 查看 Web 仪表盘日志
docker-compose logs -f web-dashboard

# 查看主机上的日志文件
tail -f ./logs/trading_system.log
```

### 健康检查

```bash
# 检查服务健康状态
docker-compose ps

# 手动健康检查
curl http://localhost:5000/api/system_status
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 仅重启交易系统
docker-compose restart trading-system

# 重新构建并启动
docker-compose up -d --build --force-recreate
```

### 更新系统

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建镜像
docker-compose build --no-cache

# 3. 重启服务
docker-compose up -d
```

## 安全建议

### 1. 网络安全

```bash
# 限制 Web 仪表盘访问
# 修改 docker-compose.yml，绑定到内网
ports:
  - "127.0.0.1:5000:5000"  # 仅本地访问

# 或使用 Nginx 反向代理 + HTTPS
```

### 2. 数据安全

- 定期备份 `./backups/` 目录
- 使用云存储服务（如 S3、OSS）备份重要数据
- 加密敏感配置文件

### 3. 访问控制

- 在生产环境添加身份验证
- 使用 VPN 访问 Web 仪表盘
- 限制 API 访问频率

## 故障排除

### 常见问题

**1. 容器无法启动**
```bash
# 查看错误日志
docker-compose logs trading-system

# 常见原因：配置文件缺失或格式错误
# 解决：检查 system_config.yaml 和 email_config.json
```

**2. Web 仪表盘无法访问**
```bash
# 检查端口是否被占用
sudo lsof -i :5000

# 检查容器状态
docker-compose ps web-dashboard

# 查看健康检查状态
docker inspect trading-dashboard | grep -A 10 Health
```

**3. 数据库锁定**
```bash
# SQLite 并发写入问题
# 解决：重启服务
docker-compose restart trading-system
```

**4. 内存不足**
```bash
# 增加交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**5. 时区问题**
```bash
# 确认容器时区
docker exec auto-trading-system date

# 如果时区不对，检查 TZ 环境变量
```

## 性能优化

### 1. 资源限制

在 `docker-compose.yml` 中添加：

```yaml
services:
  trading-system:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 2. 日志管理

```yaml
services:
  trading-system:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 3. 数据库优化

- 定期执行 VACUUM 清理 SQLite
- 考虑迁移到 PostgreSQL 以支持高并发

## 备份与恢复

### 自动备份

系统每周日自动执行备份，备份文件保存在 `./backups/` 目录。

### 手动备份

```bash
# 备份所有数据
tar -czf backup_$(date +%Y%m%d).tar.gz \
  ./data ./logs ./reports ./backups \
  ./portfolio.db ./strategy_performance.json \
  ./system_config.yaml

# 上传到云存储
aws s3 cp backup_*.tar.gz s3://your-bucket/backups/
```

### 恢复数据

```bash
# 停止服务
docker-compose down

# 恢复备份
tar -xzf backup_20240101.tar.gz

# 重启服务
docker-compose up -d
```

## 扩展功能

### 添加数据库服务

如需 PostgreSQL 支持，修改 `docker-compose.yml`：

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: trading
      POSTGRES_USER: trader
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - trading-network

volumes:
  postgres_data:
```

### 添加 Redis 缓存

```yaml
services:
  redis:
    image: redis:7-alpine
    networks:
      - trading-network
```

### 添加 Prometheus 监控

```yaml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - trading-network
```

## 技术支持

如遇到问题，请：

1. 查看 `./logs/` 目录中的日志文件
2. 检查 Docker 容器状态和健康检查
3. 确认配置文件格式正确
4. 查看本文档的故障排除部分

---

**注意**: 自动化交易涉及金融风险，请在充分理解系统行为后谨慎使用。建议先在模拟环境中测试，确保系统稳定后再用于实盘交易。
