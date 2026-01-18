# Import routers for easy access
from app.api.v1.routes import devices, ingestions, queries

__all__ = ["devices", "ingestions", "queries"]
