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

# 应用源码。data/quickform.db 为初始数据库（含默认账号），必须随镜像提供
COPY . .

# 把所有运行时状态统一归拢到 /data，原路径改为符号链接。
# 这样宿主机只需映射一个卷 /data，无需分别挂 5 个目录。
# 首次挂载空卷时 Docker 会把镜像里 /data 的初始内容复制进去。
RUN mkdir -p /data/data /data/assets /data/uploads /data/reports /data/backups \
    && cp -a /app/data/. /data/data/ \
    && cp -a /app/static/assets/. /data/assets/ \
    && cp -a /app/static/reports/. /data/reports/ \
    && rm -rf /app/data /app/static/assets /app/static/uploads /app/static/reports /app/backups \
    && ln -s /data/data /app/data \
    && ln -s /data/assets /app/static/assets \
    && ln -s /data/uploads /app/static/uploads \
    && ln -s /data/reports /app/static/reports \
    && ln -s /data/backups /app/backups

# 非 root 运行；/data 由具名卷继承该目录属主
RUN addgroup -S appuser \
    && adduser -S -G appuser -H appuser \
    && chown -R appuser:appuser /app /data

USER appuser

# 端口在 app.py:3758 硬编码为 5001，暂不支持 PORT 环境变量
EXPOSE 5001

# 所有运行时状态集中在 /data，宿主机只需映射这一个路径
VOLUME ["/data"]

# 必须以 python app.py 启动：eventlet.monkey_patch() 需先于所有导入执行，
# 换成 gunicorn/uwsgi 会破坏 WebSocket 实时推送
CMD ["python", "app.py"]
