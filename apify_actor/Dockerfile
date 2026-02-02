FROM apify/actor-python:3.11

# Upgrade pip first
RUN pip install --upgrade pip

# Pin apify SDK to a known working version that doesn't require crawlee
# Version 1.7.2 is the last version before the crawlee dependency was added
RUN pip install --no-cache-dir "apify==1.7.2" "apify-shared>=1.1.1,<2.0.0"

# Ensure pydantic is compatible (apify 1.7.2 works with pydantic 2.x)
RUN pip install --no-cache-dir "pydantic>=2.0.0,<3.0.0"

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
