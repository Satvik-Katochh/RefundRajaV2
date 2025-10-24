# parser/html_parsers/__init__.py
from .base import BaseHTMLParser
from .myntra import MyntraHTMLParser
from .hm import HMHTMLParser

# Export parsers
__all__ = ['BaseHTMLParser', 'MyntraHTMLParser', 'HMHTMLParser']
