FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    playwright \
    python-dotenv \
    gspread \
    oauth2client \
    python-telegram-bot==20.7 \
    dateparser \
    && python3 -m playwright install --with-deps

COPY . /app

CMD ["bash", "-lc", "/app/entrypoint.sh"]
