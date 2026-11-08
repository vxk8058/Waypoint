"""ASGI entry point: uvicorn backend.api.main:app --reload"""
import logging

from .app import create_app

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
