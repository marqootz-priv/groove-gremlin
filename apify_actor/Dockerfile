FROM apify/actor-python:3.11

# Upgrade pip first  
RUN pip install --upgrade pip

# Fix pydantic/crawlee compatibility issue
# Crawlee in the base image expects pydantic v1.x. Downgrade from v2.x to v1.10.x.
RUN pip uninstall -y pydantic || true
RUN pip install --no-cache-dir "pydantic==1.10.12"

# Verify the fix worked
RUN python -c "import pydantic; print(f'Pydantic version: {pydantic.__version__}')" || true

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
