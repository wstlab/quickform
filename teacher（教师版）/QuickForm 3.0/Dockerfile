# QuickForm 教师版 3.0 容器镜像
# 构建上下文请指向本目录（teacher（教师版）/QuickForm 3.0），不要指向仓库根
FROM python:3.11-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    QUICKFORM_IN_CONTAINER=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# tzdata：保证 datetime.now() 与备份文件名使用北京时间
RUN apk add --no-cache tzdata

# 全部依赖均使用 musllinux 预编译 wheel，无需 build-base 等编译工具链
# --only-binary=:all: 作为护栏：一旦某个依赖退回源码编译，构建会立即失败而不是悄悄变慢
COPY requirements.txt .
RUN pip install --only-binary=:all: -r requirements.txt

# 应用源码。data/quickform.db 为初始数据库（含默认账号），必须随镜像提供；
# 运行时通过卷挂载覆盖，首次挂载时 Docker 会自动把初始文件复制进空卷
COPY . .

# 非 root 运行；卷挂载后将由具名卷继承该目录的属主
RUN addgroup -S appuser \
    && adduser -S -G appuser -H appuser \
    && chown -R appuser:appuser /app

USER appuser

# 端口在 app.py:3758 硬编码为 5001，暂不支持 PORT 环境变量
EXPOSE 5001

# 需要持久化的运行时状态；backups/ 由备份接口按需创建
VOLUME ["/app/data", "/app/static/assets", "/app/static/uploads", "/app/static/reports", "/app/backups"]

# 必须以 python app.py 启动：eventlet.monkey_patch() 需先于所有导入执行，
# 换成 gunicorn/uwsgi 会破坏 WebSocket 实时推送
CMD ["python", "app.py"]
