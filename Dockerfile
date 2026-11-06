FROM python:3.11-slim

# Set timezone ke WIB & hindari buffer log
ENV TZ=Asia/Jakarta \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependensi sistem minimal yang diperlukan (libmagic untuk neonize, ffmpeg untuk audio/video, tzdata)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    ffmpeg \
    tzdata \
    ca-certificates \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install dependensi Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code
COPY . .

CMD ["python", "src/bot.py"]

