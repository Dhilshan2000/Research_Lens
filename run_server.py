"""ResearchLens Entrypoint Runner
Starts the FastAPI application and serves both API & React Frontend on port 8000.
Swagger UI is accessible at: http://localhost:8000/docs
React UI is accessible at:    http://localhost:8000/
"""
import sys
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)
