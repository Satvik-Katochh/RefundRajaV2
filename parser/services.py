# parser/services.py
from orders.models import Order, OrderProduct
import re
import dateparser
from decimal import Decimal
from datetime import datetime
from merchants.models import MerchantRule
from parser.html_parsers import MyntraHTMLParser, HMHTMLParser
from parser.services.order_merger import OrderMerger


class EmailParser:
    """
    Enhanced email parser with HTML-first approach and regex fallback
    """

    def __init__(self):
        # Order ID patterns - try multiple formats
        self.order_id_patterns = [
            r'Order\s*#?\s*([A-Z0-9\-]+)',           # "Order #OD12345"
            r'Order\s*ID[:\s]+([A-Z0-9\-]+)',         # "Order ID: 123-456"
            r'Your\s+order\s+([A-Z0-9\-]+)',         # "Your order OD-12345"
            r'Order\s+Number[:\s]+([A-Z0-9\-]+)',     # "Order Number: 123"
            r'Order\s+([A-Z0-9\-]+)',                # "Order 12345"
        ]

        # Date patterns
        self.date_patterns = [
            # "Delivered on 10 Oct 2025"
            r'Delivered\s+on\s+([^.\n]+)',
            # "placed on 01 Oct 2025" - matches our text
            r'placed\s+on\s+([^.\n]+)',
            # "Order placed: 01 Oct 2025"
            r'Order\s+placed[:\s]+([^.\n]+)',
            # "Order date: 01 Oct 2025"
            r'Order\s+date[:\s]+([^.\n]+)',
        ]

        # Amount patterns
        self.amount_patterns = [
            r'[₹$]\s*([0-9,]+\.?[0-9]*)',           # "₹899.00", "$29.99"
            r'Amount[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',  # "Amount: ₹899.00"
            r'Total[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',  # "Total: ₹899.00"
        ]

        # Merchant patterns (extract from email domain)
        self.merchant_patterns = {
            r'@flipkart\.com': 'Flipkart',
            r'@amazon\.in': 'Amazon',
            r'@myntra\.com': 'Myntra',
            r'@nykaa\.com': 'Nykaa',
            r'@zomato\.com': 'Zomato',
            r'@ajio\.com': 'Ajio',
            r'@hm\.com': 'H&M',
            r'@delivery\.hm\.com': 'H&M',
        }

        # HTML parsers for each merchant
        self.html_parsers = {
            'Myntra': MyntraHTMLParser(),
            'H&M': HMHTMLParser(),
            # Add more merchants here later
        }

        # Order merger for handling multiple emails
        self.order_merger = OrderMerger()

    def parse_email(self, raw_text, raw_html=None, from_email=None):
        """
        Enhanced parsing with HTML-first approach and regex fallback
        """
        merchant = self._extract_merchant(from_email)

        # Step 1: Try HTML parsing first
        if raw_html and merchant in self.html_parsers:
            html_result = self.html_parsers[merchant].parse(raw_html)
            if html_result and html_result['confidence'] > 0.7:
                return html_result

        # Step 2: Fallback to regex parsing
        return self._parse_text_fallback(raw_text, from_email)

    def _parse_text_fallback(self, raw_text, from_email):
        """
        Fallback regex-based parsing (original method)
        """
        parsed_data = {
            'merchant_name': None,
            'order_id': None,
            'order_date': None,
            'delivery_date': None,
            'amount': None,
            'currency': 'INR',
            'return_window_days': 30,  # Default
            'parsed_confidence': 0.0,
            'parsed_json': {}
        }

        # Step 1: Extract merchant from email
        merchant_name = self._extract_merchant(from_email)
        if merchant_name:
            parsed_data['merchant_name'] = merchant_name
            parsed_data['return_window_days'] = self._get_merchant_return_days(
                merchant_name)

        # Step 2: Extract order ID
        order_id = self._extract_order_id(raw_text)
        if order_id:
            parsed_data['order_id'] = order_id

        # Step 3: Extract dates
        dates = self._extract_dates(raw_text)
        if dates:
            parsed_data['order_date'] = dates.get('order_date')
            parsed_data['delivery_date'] = dates.get('delivery_date')

        # Step 4: Extract amount
        amount = self._extract_amount(raw_text)
        if amount:
            parsed_data['amount'] = amount

        # Step 5: Calculate confidence
        parsed_data['parsed_confidence'] = self._calculate_confidence(
            parsed_data)

        # Step 6: Store raw parsing info
        parsed_data['parsed_json'] = {
            'source': 'regex-parser-v1',
            'from_email': from_email,
            'patterns_used': {
                'merchant': merchant_name,
                'order_id': order_id,
                'dates': {
                    'order_date_str': dates.get('order_date_str'),
                    'delivery_date_str': dates.get('delivery_date_str')
                },
                'amount': str(amount) if amount else None
            }
        }

        return parsed_data

    def _extract_merchant(self, from_email):
        """Extract merchant name from email address"""
        for pattern, merchant_name in self.merchant_patterns.items():
            if re.search(pattern, from_email, re.IGNORECASE):
                return merchant_name
        return None

    def _extract_order_id(self, text):
        """Try multiple patterns to find order ID"""
        for pattern in self.order_id_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_dates(self, text):
        """Extract order and delivery dates"""
        dates = {}

        for pattern in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                if parsed_date:
                    # Convert to string for JSON storage
                    date_str_formatted = parsed_date.date().isoformat()
                    # Determine if it's order date or delivery date
                    if pattern.startswith(r'Delivered'):
                        dates['delivery_date'] = parsed_date.date()
                        dates['delivery_date_str'] = date_str_formatted
                    else:
                        dates['order_date'] = parsed_date.date()
                        dates['order_date_str'] = date_str_formatted

        return dates

    def _extract_amount(self, text):
        """Extract amount from text"""
        for pattern in self.amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return Decimal(amount_str)
                except:
                    continue
        return None

    def _get_merchant_return_days(self, merchant_name):
        """Get default return days from MerchantRule"""
        try:
            rule = MerchantRule.objects.get(
                merchant_name__iexact=merchant_name)
            return rule.default_return_days
        except MerchantRule.DoesNotExist:
            return 30  # Default

    def _calculate_confidence(self, parsed_data):
        """Calculate confidence score (0.0 to 1.0)"""
        confidence = 0.0

        if parsed_data.get('merchant_name'):
            confidence += 0.2
        if parsed_data.get('order_id'):
            confidence += 0.3
        if parsed_data.get('amount'):
            confidence += 0.2
        if parsed_data.get('delivery_date'):
            confidence += 0.2
        if parsed_data.get('order_date'):
            confidence += 0.1

        return min(confidence, 1.0)


# Convenience function
def parse_email(raw_text, from_email=None, raw_html=None):
    """
    Parse email and return structured data
    Supports both HTML and text parsing
    """
    parser = EmailParser()
    return parser.parse_email(raw_text, raw_html=raw_html, from_email=from_email)


def create_order_from_email(raw_email, parsed_data):
    """
    Create or update Order and OrderProduct instances from parsed email data
    Uses the new OrderMerger for handling multiple emails
    """
    merger = OrderMerger()
    return merger.create_or_update_order(raw_email.user, parsed_data, raw_email)
