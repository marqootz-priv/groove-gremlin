FROM apify/actor-python:3.11

# Upgrade pip first
RUN pip install --upgrade pip

# Fix pydantic/crawlee compatibility issue
# Use pydantic 2.0.3 (before underscore restrictions in 2.1.0)
RUN pip uninstall -y pydantic || true
RUN pip install --no-cache-dir "pydantic==2.0.3"

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
