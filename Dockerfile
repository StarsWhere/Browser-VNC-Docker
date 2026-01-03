FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    fluxbox tigervnc-standalone-server tigervnc-common tigervnc-tools novnc websockify \
    supervisor procps locales tzdata firefox-esr ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app /app
COPY docs /app/docs

RUN chmod +x /app/scripts/*.sh && chmod +x /app/scripts/*.py

EXPOSE 6080 8080

ENV DATA_DIR=/data

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
