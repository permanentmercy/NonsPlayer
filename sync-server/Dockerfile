# 使用官方超轻量 Python Alpine 镜像 (体积仅约 50MB，内存仅约 15MB)
FROM python:3.11-alpine

WORKDIR /app

# 拷贝服务端脚本
COPY server.py .

# 创建持久化数据目录
RUN mkdir -p /data
VOLUME /data

# 暴露端口
EXPOSE 17777

# 环境变量默认配置
ENV SYNC_HOST="0.0.0.0" \
    SYNC_PORT="17777" \
    SYNC_DB="/data/nons_playlists.db" \
    SYNC_TOKEN=""

# 启动命令
CMD ["python3", "server.py"]
