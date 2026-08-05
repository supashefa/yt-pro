# Start with a Python Linux environment
FROM python:3.10-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy your files into the server
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Turn on the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]