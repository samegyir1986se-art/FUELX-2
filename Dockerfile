FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV DATA_DIR=/data PORT=3000
VOLUME /data
EXPOSE 3000
CMD ["python","server.py"]
