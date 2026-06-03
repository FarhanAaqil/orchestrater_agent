FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for PyAudio and general compilation
RUN apt-get update && apt-get install -y \
    gcc \
    portaudio19-dev \
    alsa-utils \
    espeak \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 8000 as requested
EXPOSE 8000

# Run Streamlit on port 8000
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8000", "--server.address=0.0.0.0"]
