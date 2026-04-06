import os
import sys

# Add the 'backend' directory to the Python path
# This ensures that any internal imports within the backend folder work correctly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import uvicorn

if __name__ == "__main__":
    # Pterodactyl requires the server to bind to 0.0.0.0 and pass the port via SERVER_PORT
    port = int(os.environ.get("SERVER_PORT", os.environ.get("PORT", 8000)))
    
    # Run the FastAPI app located in backend/api.py
    uvicorn.run("backend.api:app", host="0.0.0.0", port=port, log_level="info")
