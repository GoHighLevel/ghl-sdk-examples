#!/usr/bin/env python
"""
Run script for GHL Webhook Django App.
"""
import os
import sys
from pathlib import Path

# Add the project directory to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

if __name__ == '__main__':
    # Import Django settings
    import django
    from django.conf import settings
    django.setup()

    # Import and run ASGI application with uvicorn
    import uvicorn
    from config.asgi import application

    port = int(os.getenv('PORT', '3003'))
    print(f"Starting Django ASGI server on http://0.0.0.0:{port}")
    uvicorn.run(
        application,
        host='0.0.0.0',
        port=port,
        log_level='info'
    )
