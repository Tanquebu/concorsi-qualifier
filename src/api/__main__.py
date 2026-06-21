"""Lancia l'API server: python -m src.api"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
