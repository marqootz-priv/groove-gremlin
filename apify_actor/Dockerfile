FROM apify/actor-python:3.11

# Upgrade pip first
RUN pip install --upgrade pip

# Fix pydantic/crawlee compatibility issue
# Crawlee in base image uses pydantic v2.1.0+ which has breaking changes
# Downgrade pydantic to v2.0.x which works with crawlee
RUN pip install --force-reinstall --no-cache-dir "pydantic>=2.0.0,<2.1.0"

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
