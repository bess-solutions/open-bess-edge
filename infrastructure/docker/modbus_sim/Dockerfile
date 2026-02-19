FROM bessai-edge-gateway:latest

WORKDIR /app
COPY server.py .

EXPOSE 502

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python -c "import socket; s=socket.create_connection(('localhost',502),2); s.close()"

CMD ["/opt/venv/bin/python", "-u", "server.py"]
