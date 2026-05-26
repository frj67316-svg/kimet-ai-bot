FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends 
    libgl1 
    libglib2.0-0 
    libsm6 
    libxrender1 
    libxext6 
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY . /app
WORKDIR /app

# Expose port
EXPOSE 7860

# Run application
CMD ["python", "src/app.py"]