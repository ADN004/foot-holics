FROM python:3.11-slim

# git is needed so the bot can commit & push after making changes
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global --add safe.directory /app \
    && git config --global --add safe.directory /foot-holics-live

WORKDIR /app

# Install Python deps first (cached layer — only rebuilds when requirements.txt changes)
COPY foot-holics-bot/requirements.txt foot-holics-bot/requirements.txt
RUN pip install --no-cache-dir -r foot-holics-bot/requirements.txt

# The actual project files are volume-mounted at runtime (see docker-compose.yml)
# so live edits on the host are reflected without rebuilding the image.

CMD ["python", "foot-holics-bot/bot.py"]
