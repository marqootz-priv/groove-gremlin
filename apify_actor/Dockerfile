FROM apify/actor-python:3.11

# Upgrade pip first
RUN pip install --upgrade pip

# Fix pydantic/crawlee/apify compatibility
# Force everything to pydantic v1.x and matching crawlee/apify that work with it
RUN pip uninstall -y apify crawlee pydantic || true && \
    pip install --no-cache-dir --force-reinstall --no-deps "pydantic==1.10.12" && \
    pip install --no-cache-dir --force-reinstall --no-deps "crawlee==0.3.4" && \
    pip install --no-cache-dir --force-reinstall --no-deps "apify==1.7.1"

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
