"""
Firebase Functions entry point for serverless deployment.
"""

from app import app

# This is the entry point for Firebase Functions
# For local development, use app.py directly
if __name__ == '__main__':
    app.run(debug=True, port=5000)
