FROM apify/actor-python:3.11

# Copy requirements first (for better caching)
COPY requirements.txt ./

# Install dependencies
# Note: apify is already installed in base image, we only install our additional deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . ./

# Set environment variables
ENV APIFY_DEFAULT_DATASET_ID=default

# Run the actor
CMD ["python", "main.py"]
