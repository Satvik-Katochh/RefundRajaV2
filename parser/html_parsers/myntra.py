# parser/html_parsers/myntra.py
from .base import BaseHTMLParser
import re
import dateparser
from decimal import Decimal


class MyntraHTMLParser(BaseHTMLParser):
    """
    Myntra-specific HTML parser
    Inherits from BaseHTMLParser
    """

    def get_merchant_name(self):
        return 'Myntra'

    def extract_order_id(self, soup):
        """Extract packet ID from Myntra email"""
        # Method 1: Look for specific ID
        order_id_element = soup.find('li', {'id': 'OrderId'})
        if order_id_element:
            return order_id_element.get_text().strip()

        # Method 2: Fallback - search in text
        text_content = soup.get_text()
        packet_pattern = re.compile(r'Your Packet Id\s*:\s*(\d+)')
        match = packet_pattern.search(text_content)
        if match:
            return match.group(1)

        return None

    def extract_order_date(self, soup):
        """Extract order date from Myntra email"""
        # For Myntra delivery emails, we usually don't have order date
        # Use delivery date as fallback
        delivery_date = self.extract_delivery_date(soup)
        return delivery_date

    def extract_delivery_date(self, soup):
        """Extract delivery date from Myntra email"""
        # Method 1: Look for specific ID
        delivery_element = soup.find('span', {'id': 'OrderDeliveredDateId'})
        if delivery_element:
            date_text = delivery_element.get_text().strip()
            # Remove "on " prefix if present
            date_text = re.sub(r'^on\s+', '', date_text)
            parsed_date = dateparser.parse(date_text)
            return parsed_date.date() if parsed_date else None

        # Method 2: Fallback - search in text
        text_content = soup.get_text()
        delivery_patterns = [
            r'Delivered.*?on\s+([^,\n]+)',
            r'Delivery.*?on\s+([^,\n]+)',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_return_deadline(self, soup):
        """Extract return deadline from invoice availability"""
        # Method 1: Look for specific ID
        available_element = soup.find('span', {'id': 'AvailableTillDateId'})
        if available_element:
            date_text = available_element.get_text().strip()
            parsed_date = dateparser.parse(date_text)
            return parsed_date.date() if parsed_date else None

        # Method 2: Fallback - search in text
        text_content = soup.get_text()
        available_pattern = re.compile(r'Available till\s+([^,\n]+)')
        match = available_pattern.search(text_content)
        if match:
            date_str = match.group(1).strip()
            parsed_date = dateparser.parse(date_str)
            return parsed_date.date() if parsed_date else None

        return None

    def extract_products(self, soup):
        """Extract product information (name, size, quantity, seller)"""
        products = []

        # Extract brand name
        brand_element = soup.find(
            'p', {'id': re.compile(r'ItemProductBrandName')})
        brand = brand_element.get_text().strip() if brand_element else ""

        # Extract product name
        product_element = soup.find(
            'span', {'id': re.compile(r'ItemProductName')})
        product = product_element.get_text().strip() if product_element else ""

        # Combine brand + product
        product_name = ""
        if brand and product:
            product_name = f"{brand} {product}".strip()
        elif product:
            product_name = product
        elif brand:
            product_name = brand

        if product_name:
            # Extract size
            size_element = soup.find('span', {'id': re.compile(r'ItemSize')})
            size = size_element.get_text().strip() if size_element else ""

            # Extract quantity
            qty_element = soup.find(
                'span', {'id': re.compile(r'ItemQuantity')})
            quantity = 1
            if qty_element:
                try:
                    quantity = int(qty_element.get_text().strip())
                except:
                    quantity = 1

            # Extract seller
            seller_element = soup.find(
                'div', {'id': re.compile(r'ItemSellerName')})
            seller = ""
            if seller_element:
                seller_text = seller_element.get_text().strip()
                # Extract seller name after "Sold by: "
                match = re.search(r'Sold by:\s*(.+)', seller_text)
                if match:
                    seller = match.group(1).strip()

            # Extract price (if available in delivery email)
            price = self.extract_amount(soup) or Decimal('0')

            products.append({
                'name': product_name,
                'size': size,
                'quantity': quantity,
                'price': price,
                'seller': seller
            })

        return products

    def extract_amount(self, soup):
        """Extract amount - Myntra delivery emails usually don't show amount"""
        # Look for amount patterns in text
        text_content = soup.get_text()
        amount_patterns = [
            r'[₹$]\s*([0-9,]+\.?[0-9]*)',
            r'Amount[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'Total[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
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

    def parse_confirmation_email(self, soup):
        """Parse Myntra confirmation email - has PRICE"""
        return {
            'merchant_name': 'Myntra',
            'order_id': self.extract_order_id_confirmation(soup),
            'order_date': self.extract_order_date_confirmation(soup),
            'delivery_date': self.extract_delivery_date_confirmation(soup),
            'amount': self.extract_amount_confirmation(soup),  # PRICE IS HERE
            'products': self.extract_products_with_prices_confirmation(soup),
            'email_type': 'confirmation',
            'confidence': 0.9,
            'parsed_json': {'source': 'html-myntra-confirmation-v1'}
        }

    def parse_shipping_email(self, soup):
        """Parse Myntra shipping email - has TRACKING"""
        return {
            'merchant_name': 'Myntra',
            'order_id': self.extract_order_id_shipping(soup),
            'tracking_number': self.extract_tracking_number_shipping(soup),
            'tracking_url': self.extract_tracking_url(soup),
            'shipping_date': self.extract_shipping_date(soup),
            'estimated_delivery': self.extract_estimated_delivery_shipping(soup),
            'logistics_partner': self.extract_logistics_partner(soup),
            'amount': self.extract_amount_shipping(soup),
            'products': self.extract_products_shipping(soup),
            'email_type': 'shipping',
            'confidence': 0.8,
            'parsed_json': {'source': 'html-myntra-shipping-v1'}
        }

    def parse_delivery_email(self, soup):
        """Parse Myntra delivery email - has RETURN DEADLINE"""
        return {
            'merchant_name': 'Myntra',
            'order_id': self.extract_order_id(soup),
            'delivery_date': self.extract_delivery_date(soup),
            'return_deadline': self.extract_return_deadline(soup),
            'products': self.extract_products_without_prices(soup),
            'email_type': 'delivery',
            'confidence': 0.9,
            'parsed_json': {'source': 'html-myntra-delivery-v1'}
        }

    def extract_tracking_number(self, soup):
        """Extract tracking number from shipping email"""
        text_content = soup.get_text()
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

    def extract_estimated_delivery(self, soup):
        """Extract estimated delivery date from shipping email"""
        text_content = soup.get_text()
        delivery_patterns = [
            r'Expected\s+delivery[:\s]+([^.\n]+)',
            r'Delivery\s+by[:\s]+([^.\n]+)',
            r'Estimated\s+delivery[:\s]+([^.\n]+)',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None
        return None

    def extract_products_with_prices(self, soup):
        """Extract products with prices from confirmation email"""
        # Use your existing extract_products method but ensure prices are included
        products = self.extract_products(soup)
        # Add price extraction logic here
        return products

    def extract_products_without_prices(self, soup):
        """Extract products without prices from delivery email"""
        # Use your existing extract_products method
        return self.extract_products(soup)

    # Confirmation email specific methods
    def extract_order_id_confirmation(self, soup):
        """Extract order ID from confirmation email"""
        # Look for OrderId element
        order_id_element = soup.find('li', {'id': 'OrderId'})
        if order_id_element:
            return order_id_element.get_text().strip()

        # Fallback to text search
        text_content = soup.get_text()
        order_patterns = [
            r'Your order ID\s*([A-Z0-9\-]+)',
            r'Order ID[:\s]+([A-Z0-9\-]+)',
            r'Order\s*#?\s*([A-Z0-9\-]+)',
        ]

        for pattern in order_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_order_date_confirmation(self, soup):
        """Extract order date from confirmation email"""
        # Look for PacketCreationTimeId element
        date_element = soup.find('span', {'id': 'PacketCreationTimeId'})
        if date_element:
            date_text = date_element.get_text().strip()
            # Remove "on " prefix if present
            date_text = re.sub(r'^on\s+', '', date_text)
            parsed_date = dateparser.parse(date_text)
            return parsed_date.date() if parsed_date else None

        # Fallback to text search
        text_content = soup.get_text()
        date_patterns = [
            r'Order.*?confirmed.*?on\s+([^,\n]+)',
            r'Order.*?placed.*?on\s+([^,\n]+)',
            r'confirmed.*?on\s+([^,\n]+)',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_delivery_date_confirmation(self, soup):
        """Extract delivery date from confirmation email"""
        # Look for CustomerPromiseTimeId element
        delivery_element = soup.find('span', {'id': 'CustomerPromiseTimeId'})
        if delivery_element:
            date_text = delivery_element.get_text().strip()
            parsed_date = dateparser.parse(date_text)
            return parsed_date.date() if parsed_date else None

        # Fallback to text search
        text_content = soup.get_text()
        delivery_patterns = [
            r'Delivery by\s+([^,\n]+)',
            r'Expected delivery\s+([^,\n]+)',
            r'Delivery\s+by\s+([^,\n]+)',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_amount_confirmation(self, soup):
        """Extract total amount from confirmation email"""
        # Look for TotalAmountValueId element
        amount_element = soup.find('div', {'id': 'TotalAmountValueId'})
        if amount_element:
            amount_text = amount_element.get_text().strip()
            amount_str = re.search(r'[₹$]?\s*([0-9,]+\.?[0-9]*)', amount_text)
            if amount_str:
                try:
                    return Decimal(amount_str.group(1).replace(',', ''))
                except:
                    pass

        # Fallback to text search
        text_content = soup.get_text()
        amount_patterns = [
            r'Total Amount[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'Net Paid[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'[₹$]\s*([0-9,]+\.?[0-9]*)\s*Total',
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

    def extract_products_with_prices_confirmation(self, soup):
        """Extract products with prices from confirmation email"""
        products = []

        # Look for product elements with specific IDs
        product_elements = soup.find_all(
            'li', {'id': re.compile(r'ItemProductDescription-\d+')})

        for product_element in product_elements:
            # Extract product ID from the element ID
            product_id_match = re.search(
                r'ItemProductDescription-(\d+)', product_element.get('id', ''))
            if not product_id_match:
                continue

            product_id = product_id_match.group(1)

            # Extract brand name
            brand_element = soup.find(
                'p', {'id': f'ItemProductBrandName-{product_id}'})
            brand = brand_element.get_text().strip() if brand_element else ""

            # Extract product name
            product_element_name = soup.find(
                'span', {'id': f'ItemProductName-{product_id}'})
            product_name = product_element_name.get_text(
            ).strip() if product_element_name else ""

            # Combine brand + product
            full_product_name = ""
            if brand and product_name:
                full_product_name = f"{brand} {product_name}".strip()
            elif product_name:
                full_product_name = product_name
            elif brand:
                full_product_name = brand

            if full_product_name:
                # Extract size
                size_element = soup.find(
                    'span', {'id': f'ItemSize-{product_id}'})
                size = size_element.get_text().strip() if size_element else ""

                # Extract quantity
                qty_element = soup.find(
                    'span', {'id': f'ItemQuantity-{product_id}'})
                quantity = 1
                if qty_element:
                    try:
                        quantity = int(qty_element.get_text().strip())
                    except:
                        quantity = 1

                # Extract price
                price_element = soup.find(
                    'span', {'id': f'ItemTotal-{product_id}'})
                price = Decimal('0')
                if price_element:
                    price_text = price_element.get_text().strip()
                    price_match = re.search(
                        r'[₹$]?\s*([0-9,]+\.?[0-9]*)', price_text)
                    if price_match:
                        try:
                            price = Decimal(
                                price_match.group(1).replace(',', ''))
                        except:
                            price = Decimal('0')

                # Extract seller
                seller_element = soup.find(
                    'div', {'id': f'ItemSellerName-{product_id}'})
                seller = ""
                if seller_element:
                    seller_text = seller_element.get_text().strip()
                    # Extract seller name after "Sold by: "
                    match = re.search(r'Sold by:\s*(.+)', seller_text)
                    if match:
                        seller = match.group(1).strip()

                products.append({
                    'name': full_product_name,
                    'size': size,
                    'quantity': quantity,
                    'price': price,
                    'seller': seller
                })

        return products

    # Shipping email specific methods
    def extract_order_id_shipping(self, soup):
        """Extract order ID from shipping email"""
        # Look for OrderId element (this is actually the tracking ID in shipping emails)
        order_id_element = soup.find('li', {'id': 'OrderId'})
        if order_id_element:
            return order_id_element.get_text().strip()

        # Fallback to text search
        text_content = soup.get_text()
        order_patterns = [
            r'Your Tracking Id[:\s]+([A-Z0-9\-]+)',
            r'Tracking Id[:\s]+([A-Z0-9\-]+)',
            r'Order ID[:\s]+([A-Z0-9\-]+)',
        ]

        for pattern in order_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_tracking_number_shipping(self, soup):
        """Extract tracking number from shipping email"""
        # Look for OrderId element (this is the tracking ID)
        tracking_element = soup.find('li', {'id': 'OrderId'})
        if tracking_element:
            return tracking_element.get_text().strip()

        # Fallback to text search
        text_content = soup.get_text()
        tracking_patterns = [
            r'Your Tracking Id[:\s]+([A-Z0-9\-]+)',
            r'Tracking Id[:\s]+([A-Z0-9\-]+)',
            r'Tracking Number[:\s]+([A-Z0-9\-]+)',
        ]

        for pattern in tracking_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_shipping_date(self, soup):
        """Extract shipping date from shipping email"""
        # Look for PacketCreationTimeId element
        date_element = soup.find('span', {'id': 'PacketCreationTimeId'})
        if date_element:
            date_text = date_element.get_text().strip()
            # Remove "on " prefix if present
            date_text = re.sub(r'^on\s+', '', date_text)
            parsed_date = dateparser.parse(date_text)
            return parsed_date.date() if parsed_date else None

        # Fallback to text search
        text_content = soup.get_text()
        date_patterns = [
            r'Shipped.*?on\s+([^,\n]+)',
            r'Order.*?shipped.*?on\s+([^,\n]+)',
            r'shipped.*?on\s+([^,\n]+)',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_estimated_delivery_shipping(self, soup):
        """Extract estimated delivery date from shipping email"""
        # Look for CustomerPromiseTimeId element
        delivery_element = soup.find('span', {'id': 'CustomerPromiseTimeId'})
        if delivery_element:
            date_text = delivery_element.get_text().strip()
            parsed_date = dateparser.parse(date_text)
            return parsed_date.date() if parsed_date else None

        # Fallback to text search
        text_content = soup.get_text()
        delivery_patterns = [
            r'Delivery by\s+([^,\n]+)',
            r'Expected delivery\s+([^,\n]+)',
            r'Delivery\s+by\s+([^,\n]+)',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = dateparser.parse(date_str)
                return parsed_date.date() if parsed_date else None

        return None

    def extract_logistics_partner(self, soup):
        """Extract logistics partner from shipping email"""
        # Look for CourierDisplayNameId element
        courier_element = soup.find('span', {'id': 'CourierDisplayNameId'})
        if courier_element:
            return courier_element.get_text().strip()

        # Fallback to text search
        text_content = soup.get_text()
        courier_patterns = [
            r'Logistic Partner[:\s]+(.+)',
            r'Courier[:\s]+(.+)',
            r'Shipping Partner[:\s]+(.+)',
        ]

        for pattern in courier_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def extract_tracking_url(self, soup):
        """Extract tracking URL from shipping email"""
        # Look for "TRACK MY ORDER" button
        track_button = soup.find('a', string=re.compile(r'TRACK.*ORDER', re.I))
        if track_button:
            return track_button.get('href')

        # Look for tracking links in href attributes
        tracking_links = soup.find_all(
            'a', href=re.compile(r'track|shipping', re.I))
        for link in tracking_links:
            href = link.get('href', '')
            if 'track' in href.lower() or 'shipping' in href.lower():
                return href

        # Look for Myntra tracking URLs
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if 'myntra.com' in href and ('track' in href.lower() or 'order' in href.lower()):
                return href

        return None

    def extract_amount_shipping(self, soup):
        """Extract total amount from shipping email"""
        # Look for TotalAmountValueId element
        amount_element = soup.find('strong', {'id': 'TotalAmountValueId'})
        if amount_element:
            amount_text = amount_element.get_text().strip()
            amount_str = re.search(r'[₹$]?\s*([0-9,]+\.?[0-9]*)', amount_text)
            if amount_str:
                try:
                    return Decimal(amount_str.group(1).replace(',', ''))
                except:
                    pass

        # Fallback to text search
        text_content = soup.get_text()
        amount_patterns = [
            r'Total paid[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'Total Amount[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]*)',
            r'[₹$]\s*([0-9,]+\.?[0-9]*)\s*Total',
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

    def extract_products_shipping(self, soup):
        """Extract products from shipping email"""
        products = []

        # Look for product elements with specific IDs
        product_elements = soup.find_all(
            'li', {'id': re.compile(r'ItemProductBrandName-\d+')})

        for product_element in product_elements:
            # Extract product ID from the element ID
            product_id_match = re.search(
                r'ItemProductBrandName-(\d+)', product_element.get('id', ''))
            if not product_id_match:
                continue

            product_id = product_id_match.group(1)

            # Extract brand name
            brand_element = soup.find(
                'p', {'id': f'ItemProductBrandName-{product_id}'})
            brand = brand_element.get_text().strip() if brand_element else ""

            # Extract product name
            product_element_name = soup.find(
                'span', {'id': f'ItemProductName-{product_id}'})
            product_name = product_element_name.get_text(
            ).strip() if product_element_name else ""

            # Combine brand + product
            full_product_name = ""
            if brand and product_name:
                full_product_name = f"{brand} {product_name}".strip()
            elif product_name:
                full_product_name = product_name
            elif brand:
                full_product_name = brand

            if full_product_name:
                # Extract size
                size_element = soup.find(
                    'span', {'id': f'ItemSize-{product_id}'})
                size = size_element.get_text().strip() if size_element else ""

                # Extract quantity
                qty_element = soup.find(
                    'span', {'id': f'ItemQuantity-{product_id}'})
                quantity = 1
                if qty_element:
                    try:
                        quantity = int(qty_element.get_text().strip())
                    except:
                        quantity = 1

                # Extract seller
                seller_element = soup.find(
                    'div', {'id': f'ItemSellerName-{product_id}'})
                seller = ""
                if seller_element:
                    seller_text = seller_element.get_text().strip()
                    # Extract seller name after "Sold by: "
                    match = re.search(r'Sold by:\s*(.+)', seller_text)
                    if match:
                        seller = match.group(1).strip()

                products.append({
                    'name': full_product_name,
                    'size': size,
                    'quantity': quantity,
                    # Shipping emails don't have individual product prices
                    'price': Decimal('0'),
                    'seller': seller
                })

        return products
