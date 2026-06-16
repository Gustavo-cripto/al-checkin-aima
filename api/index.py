"""Entrypoint serverless para a Vercel (@vercel/python).

A Vercel serve a aplicação WSGI exposta na variável `app`. Importamos a app
Flask definida em app.py (na raiz do projeto).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402  (a app Flask que a Vercel vai servir)
