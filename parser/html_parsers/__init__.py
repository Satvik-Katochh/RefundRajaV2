# parser/html_parsers/__init__.py
from .base import BaseHTMLParser
from .myntra import MyntraHTMLParser

# Export parsers
__all__ = ['BaseHTMLParser', 'MyntraHTMLParser']
