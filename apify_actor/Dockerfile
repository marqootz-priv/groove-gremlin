FROM apify/actor-python:3.11

# Upgrade pip first
RUN pip install --upgrade pip

# Fix apify/apify_shared version mismatch
# The base image has incompatible versions - upgrade both to latest compatible versions
RUN pip install --upgrade --no-cache-dir apify apify-shared

# Fix pydantic compatibility - downgrade to avoid underscore restriction
RUN pip uninstall -y pydantic || true
RUN pip install --no-cache-dir "pydantic>=2.0.0,<2.1.0"

# Copy requirements first (for better caching)
COPY requirements.txt ./

# Install our additional dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . ./

# Set environment variables
ENV APIFY_DEFAULT_DATASET_ID=default

# Run the actor
CMD ["python", "main.py"]
