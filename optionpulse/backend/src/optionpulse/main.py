"""ASGI entry point: ``uvicorn optionpulse.main:app``."""

from .api import create_app

app = create_app()
