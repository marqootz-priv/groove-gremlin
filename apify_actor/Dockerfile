FROM apify/actor-python:3.11

# Upgrade pip first
RUN pip install --upgrade pip

# Fix pydantic compatibility - only downgrade pydantic, don't touch apify/crawlee
# The base image has apify/crawlee that work together, we just need compatible pydantic
# Use pydantic 2.0.3 which is before the underscore restriction (2.1.0+)
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
