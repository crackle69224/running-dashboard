"""WSGI adapter so the FastAPI (ASGI) app can run on PythonAnywhere, whose
free-tier web server only speaks WSGI."""
from a2wsgi import ASGIMiddleware

from app.main import app as asgi_app

application = ASGIMiddleware(asgi_app)
