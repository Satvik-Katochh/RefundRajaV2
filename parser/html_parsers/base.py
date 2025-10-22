# parser/html_parsers/base.py
from bs4 import BeautifulSoup
import re
import dateparser
from abc import ABC, abstractmethod
from .email_type_detector import EmailTypeDetector  # ADD THIS IMPORT


class BaseHTMLParser(ABC):
    """Enhanced base parser with email type support"""

    def __init__(self):
        self.merchant_name = self.get_merchant_name()
        self.type_detector = EmailTypeDetector()  # ADD THIS LINE

    def parse(self, html_content):
        """Main parsing method with email type detection"""
        soup = BeautifulSoup(html_content, 'html.parser')
        email_type = self.type_detector.detect_email_type(
            soup)  # ADD THIS LINE

        # Extract data based on email type
        if email_type == "confirmation":
            return self.parse_confirmation_email(soup)
        elif email_type == "shipping":
            return self.parse_shipping_email(soup)
        elif email_type == "delivery":
            return self.parse_delivery_email(soup)
        else:
            return self.parse_generic_email(soup)

    # ADD THESE NEW ABSTRACT METHODS
    @abstractmethod
    def parse_confirmation_email(self, soup):
        """Parse confirmation email - has PRICE"""
        pass

    @abstractmethod
    def parse_shipping_email(self, soup):
        """Parse shipping email - has TRACKING"""
        pass

    @abstractmethod
    def parse_delivery_email(self, soup):
        """Parse delivery email - has RETURN DEADLINE"""
        pass

    def parse_generic_email(self, soup):
        """Fallback for unknown email types"""
        return {
            'merchant_name': self.merchant_name,
            'order_id': self.extract_order_id(soup),
            'order_date': self.extract_order_date(soup),
            'delivery_date': self.extract_delivery_date(soup),
            'return_deadline': self.extract_return_deadline(soup),
            'products': self.extract_products(soup),
            'amount': self.extract_amount(soup),
            'currency': 'INR',
            'email_type': 'unknown',
            'confidence': 0.5,
            'parsed_json': {'source': f'html-{self.merchant_name.lower()}-generic'}
        }

    # Original abstract methods that each merchant parser must implement
    @abstractmethod
    def get_merchant_name(self):
        """Override in each merchant parser"""
        return "Unknown"

    @abstractmethod
    def extract_order_id(self, soup):
        """Override in each merchant parser"""
        return None

    @abstractmethod
    def extract_order_date(self, soup):
        """Override in each merchant parser"""
        return None

    @abstractmethod
    def extract_delivery_date(self, soup):
        """Override in each merchant parser"""
        return None

    @abstractmethod
    def extract_return_deadline(self, soup):
        """Override in each merchant parser"""
        return None

    @abstractmethod
    def extract_products(self, soup):
        """Override in each merchant parser - return list of product dicts"""
        return []

    @abstractmethod
    def extract_amount(self, soup):
        """Override in each merchant parser"""
        return None

    def calculate_confidence(self, result):
        """Calculate confidence score (0.0 to 1.0)"""
        confidence = 0.0

        if result.get('merchant_name'):
            confidence += 0.1
        if result.get('order_id'):
            confidence += 0.3
        if result.get('delivery_date'):
            confidence += 0.2
        if result.get('return_deadline'):
            confidence += 0.2
        if result.get('products'):
            confidence += 0.1
        if result.get('amount'):
            confidence += 0.1

        return min(confidence, 1.0)
