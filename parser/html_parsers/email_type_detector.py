# parser/html_parsers/email_type_detector.py
import re


class EmailTypeDetector:
    """Universal email type detection for all merchants"""

    EMAIL_TYPE_PATTERNS = {
        'confirmation': [
            'order confirmed', 'order placed', 'order received',
            'payment successful', 'order confirmation', 'thank you for your order',
            'order details', 'order summary'
        ],
        'shipping': [
            'shipped', 'dispatched', 'on the way', 'in transit',
            'tracking', 'shipment', 'out for delivery', 'track your order'
        ],
        'delivery': [
            'delivered', 'delivery successful', 'package delivered',
            'order delivered', 'received your order', 'delivered successfully',
            'available till', 'return window', 'return policy'
        ]
    }

    def detect_email_type(self, soup):
        """Detect email type from HTML content"""
        text = soup.get_text().lower()

        # Check for specific HTML IDs that indicate email type
        if soup.find('span', {'id': 'AvailableTillDateId'}):
            return 'delivery'
        if soup.find('span', {'id': 'OrderDeliveredDateId'}):
            return 'delivery'
        if soup.find('span', {'id': 'CourierDisplayNameId'}):
            return 'shipping'
        if soup.find('span', {'id': re.compile(r'.*Tracking.*', re.I)}):
            return 'shipping'
        if soup.find('li', {'id': 'OrderId'}) and 'shipped' in text:
            return 'shipping'
        if soup.find('li', {'id': 'OrderId'}):
            return 'confirmation'
        if soup.find('span', {'id': 'PacketCreationTimeId'}):
            return 'confirmation'
        if soup.find('span', {'id': 'CustomerPromiseTimeId'}):
            return 'confirmation'

        # Fallback to text pattern matching
        for email_type, patterns in self.EMAIL_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    return email_type

        return 'unknown'
