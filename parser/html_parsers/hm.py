# parser/html_parsers/hm.py
from .base import BaseHTMLParser
import re
import dateparser
from decimal import Decimal


class HMHTMLParser(BaseHTMLParser):
    """
    H&M-specific HTML parser
    Inherits from BaseHTMLParser
    Strategy: Single email (delivery email has everything)
    """

    def get_merchant_name(self):
        return 'H&M'

    def extract_order_id(self, soup):
        """Extract order ID from H&M email"""
        # Look for order ID patterns in H&M emails
        text_content = soup.get_text()

        # H&M order ID patterns
        order_patterns = [
            r'Order\s+Number[:\s]+(\d+)',
            r'Order\s+ID[:\s]+(\d+)',
            r'Order\s+#?\s*(\d+)',
            r'Your\s+order\s+(\d+)',
        ]

        for pattern in order_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_order_date(self, soup):
        """Extract order date from H&M email"""
        text_content = soup.get_text()

        # H&M order date patterns
        date_patterns = [
            r'Order\s+date[:\s]+([^.\n]+)',
            r'Ordered\s+on[:\s]+([^.\n]+)',
            r'Order\s+placed[:\s]+([^.\n]+)',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_delivery_date(self, soup):
        """Extract delivery date from H&M email"""
        text_content = soup.get_text()

        # H&M delivery date patterns
        delivery_patterns = [
            r'Delivered\s+on[:\s]+([^.\n]+)',
            r'Delivery\s+date[:\s]+([^.\n]+)',
            r'Package\s+delivered[:\s]+([^.\n]+)',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_return_deadline(self, soup):
        """Extract return deadline from H&M email"""
        text_content = soup.get_text()

        # H&M return deadline patterns
        return_patterns = [
            r'Return\s+by[:\s]+([^.\n]+)',
            r'Return\s+deadline[:\s]+([^.\n]+)',
            r'Available\s+till[:\s]+([^.\n]+)',
            r'Return\s+window[:\s]+([^.\n]+)',
        ]

        for pattern in return_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_products(self, soup):
        """Extract product information from H&M email"""
        products = []

        # Look for product information in H&M emails
        # This is a simplified version - you'll need to adapt based on actual H&M email structure

        # Try to find product names
        product_elements = soup.find_all(
            ['p', 'div', 'span'], string=re.compile(r'[A-Za-z].*', re.I))

        for element in product_elements:
            text = element.get_text().strip()
            # Skip if it's too short or looks like metadata
            if len(text) < 5 or any(skip in text.lower() for skip in ['order', 'delivery', 'return', 'total', 'amount']):
                continue

            # Extract size if present
            size_match = re.search(r'Size[:\s]*([A-Z0-9]+)', text, re.I)
            size = size_match.group(1) if size_match else ""

            # Extract quantity if present
            qty_match = re.search(r'Qty[:\s]*(\d+)', text, re.I)
            quantity = int(qty_match.group(1)) if qty_match else 1

            products.append({
                'name': text,
                'size': size,
                'quantity': quantity,
                'price': Decimal('0'),  # Will be updated from amount
                'seller': 'H&M'
            })

        # If no products found, create a default one
        if not products:
            products.append({
                'name': 'H&M Product',
                'size': '',
                'quantity': 1,
                'price': Decimal('0'),
                'seller': 'H&M'
            })

        return products

    def distribute_amount_to_products(self, products, total_amount):
        """Distribute total amount among products for H&M single email strategy"""
        if not products or total_amount == 0:
            return products

        # For H&M, we'll distribute the total amount equally among products
        amount_per_product = total_amount / len(products)

        for product in products:
            product['price'] = amount_per_product

        return products

    def extract_amount(self, soup):
        """Extract total amount from H&M email"""
        text_content = soup.get_text()

        # H&M amount patterns
        amount_patterns = [
            r'Total[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'Amount[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'[₹$]\s*([0-9,]+\.?[0-9]*)\s*Total',
            r'[₹$]\s*([0-9,]+\.?[0-9]*)',
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return Decimal(amount_str)
                except:
                    continue

        return None

    def extract_tracking_number(self, soup):
        """Extract tracking number from H&M email"""
        text_content = soup.get_text()

        # H&M tracking patterns
        tracking_patterns = [
            r'Tracking\s+Number[:\s]+([A-Z0-9\-]+)',
            r'Track\s+ID[:\s]+([A-Z0-9\-]+)',
            r'Tracking\s+ID[:\s]+([A-Z0-9\-]+)',
        ]

        for pattern in tracking_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_tracking_url(self, soup):
        """Extract tracking URL from H&M email"""
        # Look for tracking links
        tracking_links = soup.find_all(
            'a', href=re.compile(r'track|shipping', re.I))
        for link in tracking_links:
            href = link.get('href', '')
            if 'track' in href.lower() or 'shipping' in href.lower():
                return href

        # Look for H&M tracking URLs
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if 'hm.com' in href and ('track' in href.lower() or 'order' in href.lower()):
                return href

        return None

    # H&M Strategy: Single email (delivery email has everything)
    def parse_confirmation_email(self, soup):
        """H&M confirmation email - same as delivery (single email strategy)"""
        return self.parse_delivery_email(soup)

    def parse_shipping_email(self, soup):
        """H&M shipping email - same as delivery (single email strategy)"""
        return self.parse_delivery_email(soup)

    def parse_delivery_email(self, soup):
        """H&M delivery email - has EVERYTHING (prices, tracking, return deadline)"""
        amount = self.extract_amount(soup)
        products = self.extract_products(soup)

        # Distribute amount among products for H&M single email strategy
        products = self.distribute_amount_to_products(
            products, amount or Decimal('0'))

        return {
            'merchant_name': 'H&M',
            'order_id': self.extract_order_id(soup),
            'order_date': self.extract_order_date(soup),
            'delivery_date': self.extract_delivery_date(soup),
            'return_deadline': self.extract_return_deadline(soup),
            'amount': amount,  # PRICE IS HERE
            'products': products,
            'tracking_number': self.extract_tracking_number(soup),
            'tracking_url': self.extract_tracking_url(soup),
            'email_type': 'delivery',
            'confidence': 0.95,  # High confidence - complete data
            'parsed_json': {'source': 'html-hm-delivery-v1'}
        }
