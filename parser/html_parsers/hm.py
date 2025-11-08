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
        """
        Extract product information from H&M email using hybrid approach

        Strategy (in order of reliability):
        1. Product links (href contains productpage pattern) - MOST RELIABLE
        2. Product table rows (pl-articles-table-row class)
        3. Table structure with product info
        4. Div structure with product info
        5. Smart text analysis (fallback)
        """
        print("\n[PARSER] === Extracting Products from H&M Email ===")
        products = []

        # Comprehensive skip keywords (based on actual HTML analysis)
        skip_keywords = [
            'complete the look', 'shop by', 'women', 'men', 'kids',
            'download', 'android', 'ios', 'stores', 'services',
            'find a store', 'contact', 'footer', 'header',
            'mode of payment', 'your details', 'we hope',
            'carrier has informed', 'tracking', 'order number',
            'delivery', 'return by', 'total', 'amount', 'delivered by',
            'hm.com', 'www.', 'http', 'https', 'unsubscribe',
            'privacy', 'terms', 'conditions', 'copyright',
            'standard delivery', 'delivery method', 'tracking number',
            'would you like to return', 'register return', 'have your say',
            # Confirmation email specific text
            'your order has been confirmed', 'order confirmed', 'order confirmation',
            'thank you for shopping', 'thank you for your order',
            'we have received your order', 'order has been placed',
            'order placed', 'order received', 'payment successful',
            'order details', 'order summary', 'estimated delivery',
            # Financial summary terms (should NOT be extracted as products)
            'order value', 'shipping & handling', 'shipping and handling',
            'subtotal', 'grand total', 'items total', 'item total',
            'shipping charges', 'delivery charges', 'handling',
            'tax', 'gst', 'vat', 'discount', 'coupon'
        ]

        # Helper function to check for duplicates
        def is_duplicate(name, price):
            """Check if product already exists (same name and similar price)"""
            for p in products:
                if p['name'] == name and abs(float(p['price']) - float(price)) < 1:
                    return True
            return False

        # Helper function to validate product name (not a financial term or invalid)
        def is_valid_product_name(name):
            """Validate that name is actually a product, not a financial summary term"""
            if not name or len(name) < 3:
                return False
            
            name_lower = name.lower().strip()
            
            # Check against skip keywords
            if any(skip in name_lower for skip in skip_keywords):
                return False
            
            # Financial summary patterns (exact matches or contains)
            financial_terms = [
                'order value', 'shipping', 'handling', 'subtotal', 
                'grand total', 'items total', 'item total', 'total',
                'tax', 'gst', 'vat', 'discount', 'coupon', 'charges'
            ]
            if any(term in name_lower for term in financial_terms):
                return False
            
            # Should have at least one letter (not just numbers/symbols)
            if not re.search(r'[A-Za-z]', name):
                return False
            
            # Should not be all numbers or mostly symbols
            if re.match(r'^[\d\s\-\.,₹$]+$', name):
                return False
            
            return True

        # Method 1: PRODUCT LINKS (MOST RELIABLE - based on actual HTML)
        print(f"[PARSER] Method 1: Searching product links...")
        # More flexible patterns - href might be URL-encoded or in redirect URLs
        product_link_patterns = [
            r'productpage\.\d+',           # productpage.0972640084
            r'productpage/\d+',            # productpage/0972640084
            r'hm\.com.*productpage',       # hm.com/...productpage...
            r'/productpage/',              # any /productpage/ path
            r'productpage',                # just "productpage" anywhere in URL
        ]

        all_links = soup.find_all('a', href=True)
        product_links_found = []

        for link in all_links:
            href = link.get('href', '')
            # Decode URL if needed
            try:
                from urllib.parse import unquote
                href_decoded = unquote(href)
            except:
                href_decoded = href

            # Check if link matches any product pattern
            if any(re.search(pattern, href_decoded, re.I) for pattern in product_link_patterns):
                product_links_found.append(link)

        print(f"[PARSER] Found {len(product_links_found)} product link(s)")

        for link in product_links_found:
            # Get parent container (td, div, or table)
            parent = link.find_parent(['td', 'div', 'table', 'tr'])
            if not parent:
                continue

            # Get parent text for price extraction
            parent_text = parent.get_text()

            # Extract product name - look in link's child elements first (most reliable)
            product_name = None

            # Method A: Look for <p> tags inside the link (H&M structure)
            p_tags = link.find_all('p')
            for p in p_tags:
                p_text = p.get_text().strip()
                if p_text and 5 <= len(p_text) <= 80:
                    p_lower = p_text.lower()
                    # Skip if it's a skip keyword or looks like price/size
                    if any(skip in p_lower for skip in skip_keywords):
                        continue
                    # Price or size only
                    if re.search(r'^[₹$]', p_text) or re.search(r'^\d+$', p_text):
                        continue
                    if re.search(r'[A-Za-z]', p_text):
                        # This looks like a product name
                        product_name = p_text
                        break

            # Method B: Use link text if no <p> found
            if not product_name:
                link_text = link.get_text().strip()
                if link_text and 3 <= len(link_text) <= 80:
                    if not any(skip in link_text.lower() for skip in skip_keywords):
                        if re.search(r'[A-Za-z]', link_text):
                            product_name = link_text

            # Method C: Look in parent container
            if not product_name:
                lines = [l.strip()
                         for l in parent_text.split('\n') if l.strip()]
                for line in lines[:5]:  # First 5 lines
                    line_lower = line.lower()
                    if any(skip in line_lower for skip in skip_keywords):
                        continue
                    if 5 <= len(line) <= 80 and re.search(r'[A-Za-z]', line):
                        # Check if it's not all caps or has multiple words
                        if not line.isupper() or len(line.split()) > 1:
                            product_name = line
                            break

            if not product_name:
                continue

            # Extract price from parent container (limit to 2 decimal places)
            price = Decimal('0')
            price_match = re.search(
                r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})', parent_text)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                try:
                    price = Decimal(price_str).quantize(Decimal('0.01'))
                except:
                    pass

            # Skip if price is invalid (too large or too small)
            if price > 5000 or price < 50:
                continue

            # Check for duplicates
            if is_duplicate(product_name, price):
                continue

            # Extract size (M, L, S, XL, or numeric)
            size = ""
            size_patterns = [
                r'\b([SMXL]{1,2})\b',  # S, M, L, XL
                r'Size[:\s]*([A-Z0-9\-\.]+)',
            ]
            for pattern in size_patterns:
                size_match = re.search(pattern, parent_text, re.I)
                if size_match:
                    potential_size = size_match.group(1).strip()
                    if len(potential_size) <= 10:
                        size = potential_size
                        break

            # Only add if we have valid product name AND price
            if product_name and price > 0 and is_valid_product_name(product_name):
                products.append({
                    'name': product_name,
                    'size': size,
                    'quantity': 1,
                    'price': price,
                    'seller': 'H&M'
                })
                print(
                    f"[PARSER] ✓ Product (link): {product_name[:40]}... (₹{price}, Size: {size or 'N/A'})")
            elif product_name and not is_valid_product_name(product_name):
                print(f"[PARSER] ⚠️  Skipped invalid product name: {product_name[:40]}...")

        # Method 2: Product table rows (pl-articles-table-row class - H&M specific)
        if len(products) == 0:
            print(f"[PARSER] Method 2: Searching product table rows...")
            product_rows = soup.find_all(
                'tr', class_=re.compile(r'pl-articles-table-row', re.I))

            for row in product_rows:
                row_text = row.get_text()

                # Extract price (limit to 2 decimal places)
                price_match = re.search(
                    r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})', row_text)
                if not price_match:
                    continue

                price_str = price_match.group(1).replace(',', '')
                try:
                    price_value = Decimal(price_str).quantize(Decimal('0.01'))
                except:
                    continue

                if price_value > 5000 or price_value < 50:
                    continue

                # Extract product name (first non-skip line)
                lines = [l.strip() for l in row_text.split('\n') if l.strip()]
                product_name = None

                for line in lines:
                    line_lower = line.lower()
                    if any(skip in line_lower for skip in skip_keywords):
                        continue
                    if 5 <= len(line) <= 80 and re.search(r'[A-Za-z]', line):
                        # Check if it looks like a product name
                        if not line.isdigit() and (not line.isupper() or len(line.split()) > 1):
                            product_name = line
                            break

                if product_name and is_valid_product_name(product_name):
                    # Check for duplicates
                    if is_duplicate(product_name, price_value):
                        continue

                    # Extract size
                    size = ""
                    size_match = re.search(
                        r'\b([SMXL]{1,2})\b', row_text, re.I)
                    if size_match:
                        size = size_match.group(1)

                    products.append({
                        'name': product_name,
                        'size': size,
                        'quantity': 1,
                        'price': price_value,
                        'seller': 'H&M'
                    })
                    print(
                        f"[PARSER] ✓ Product (table-row): {product_name[:40]}... (₹{price_value})")
                elif product_name and not is_valid_product_name(product_name):
                    print(f"[PARSER] ⚠️  Skipped invalid product name: {product_name[:40]}...")

        # Method 3: Table structure analysis (ONLY if no products found yet)
        if len(products) == 0:
            print(f"[PARSER] Method 3: Searching table structures...")
            # Only look at tables that might contain products (not footer/header tables)
            tables = soup.find_all('table')
            for table in tables:
                # Skip very small tables (likely layout/spacer tables)
                table_text = table.get_text()
                if len(table_text) < 20:
                    continue

                rows = table.find_all('tr')
                for row in rows:
                    row_text = row.get_text()

                    # Skip rows that are too short or too long (likely not product rows)
                    if len(row_text) < 10 or len(row_text) > 500:
                        continue

                    # Check if row has price pattern (limit to 2 decimal places)
                    price_match = re.search(
                        r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})', row_text)
                    if not price_match:
                        continue

                    price_str = price_match.group(1).replace(',', '')
                    try:
                        price_value = Decimal(
                            price_str).quantize(Decimal('0.01'))
                    except:
                        continue

                    if price_value > 5000 or price_value < 50:
                        continue

                    # Extract product name from row (before price)
                    price_pos = price_match.start()
                    before_price = row_text[:price_pos].strip()

                    lines = [l.strip()
                             for l in before_price.split('\n') if l.strip()]
                    product_name = None

                    for line in reversed(lines):
                        line_lower = line.lower()
                        if any(skip in line_lower for skip in skip_keywords):
                            continue
                        if 3 <= len(line) <= 80 and re.search(r'[A-Za-z]', line):
                            if not line.isupper() or len(line.split()) > 1:
                                product_name = line
                                break

                    if product_name and is_valid_product_name(product_name):
                        # Check for duplicates
                        if is_duplicate(product_name, price_value):
                            continue

                        size = ""
                        size_match = re.search(
                            r'\b([SMXL]{1,2})\b', row_text, re.I)
                        if size_match:
                            size = size_match.group(1)

                        products.append({
                            'name': product_name,
                            'size': size,
                            'quantity': 1,
                            'price': price_value,
                            'seller': 'H&M'
                        })
                        print(
                            f"[PARSER] ✓ Product (table): {product_name[:40]}... (₹{price_value})")
                    elif product_name and not is_valid_product_name(product_name):
                        print(f"[PARSER] ⚠️  Skipped invalid product name: {product_name[:40]}...")

        # Method 4: Div structure analysis
        if len(products) == 0:
            print(f"[PARSER] Method 4: Searching div structures...")
            divs = soup.find_all('div')
            for div in divs:
                div_text = div.get_text()
                if len(div_text) < 10 or len(div_text) > 500:
                    continue

                price_match = re.search(
                    r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})', div_text)
                if not price_match:
                    continue

                price_str = price_match.group(1).replace(',', '')
                try:
                    price_value = Decimal(price_str).quantize(Decimal('0.01'))
                except:
                    continue

                if price_value > 5000 or price_value < 50:
                    continue

                price_pos = price_match.start()
                before_price = div_text[:price_pos].strip()

                lines = [l.strip()
                         for l in before_price.split('\n') if l.strip()]
                product_name = None

                for line in reversed(lines[-3:]):
                    line_lower = line.lower()
                    if any(skip in line_lower for skip in skip_keywords):
                        continue
                    if 5 <= len(line) <= 80 and re.search(r'[A-Za-z]', line):
                        product_name = line
                        break

                if product_name and is_valid_product_name(product_name):
                    # Check for duplicates
                    if is_duplicate(product_name, price_value):
                        continue

                    products.append({
                        'name': product_name,
                        'size': '',
                        'quantity': 1,
                        'price': price_value,
                        'seller': 'H&M'
                    })
                    print(
                        f"[PARSER] ✓ Product (div): {product_name[:40]}... (₹{price_value})")
                elif product_name and not is_valid_product_name(product_name):
                    print(f"[PARSER] ⚠️  Skipped invalid product name: {product_name[:40]}...")

        # Method 5: Smart text analysis (last resort)
        if len(products) == 0:
            print(f"[PARSER] Method 5: Smart text pattern analysis...")
            text_content = soup.get_text()
            price_matches = list(re.finditer(
                r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})', text_content))

            for price_match in price_matches:
                price_str = price_match.group(1).replace(',', '')
                try:
                    price_value = Decimal(price_str).quantize(Decimal('0.01'))
                except:
                    continue

                if price_value > 5000 or price_value < 50:
                    continue

                start_pos = max(0, price_match.start() - 300)
                end_pos = min(len(text_content), price_match.end() + 50)
                context = text_content[start_pos:end_pos]

                lines = [l.strip() for l in context.split('\n') if l.strip()]
                product_name = None

                price_line_idx = None
                for i, line in enumerate(lines):
                    if price_match.group(0) in line:
                        price_line_idx = i
                        break

                if price_line_idx is not None:
                    for i in range(max(0, price_line_idx - 5), price_line_idx):
                        line = lines[i]
                        line_lower = line.lower()
                        if any(skip in line_lower for skip in skip_keywords):
                            continue
                        if 5 <= len(line) <= 80 and re.search(r'[A-Za-z]', line):
                            words = line.split()
                            if len(words) >= 1 and not line.isdigit():
                                product_name = line
                                break

                if product_name and is_valid_product_name(product_name):
                    # Check for duplicates
                    if is_duplicate(product_name, price_value):
                        continue

                    products.append({
                        'name': product_name,
                        'size': '',
                        'quantity': 1,
                        'price': price_value,
                        'seller': 'H&M'
                    })
                    print(
                        f"[PARSER] ✓ Product (text): {product_name[:40]}... (₹{price_value})")
                elif product_name and not is_valid_product_name(product_name):
                    print(f"[PARSER] ⚠️  Skipped invalid product name: {product_name[:40]}...")

        print(
            f"[PARSER] Total: {len(products)} product(s) extracted (before deduplication)")

        # DEDUPLICATE: Merge products with same name + price (within 1 rupee tolerance)
        # Group by name and similar price, sum quantities
        deduplicated = {}
        for product in products:
            name = product['name']
            price = float(product['price'])

            # Find existing product with same name and similar price (within ₹1)
            found_match = False
            for key, existing in deduplicated.items():
                existing_price = float(existing['price'])
                # Match if same name and price within ₹1
                if existing['name'] == name and abs(existing_price - price) < 1.0:
                    # Merge: sum quantities, keep higher price (more accurate)
                    existing['quantity'] = existing.get(
                        'quantity', 1) + product.get('quantity', 1)
                    if price > existing_price:
                        existing['price'] = Decimal(
                            str(price)).quantize(Decimal('0.01'))
                    found_match = True
                    print(
                        f"[PARSER] Merged duplicate: {name[:40]}... (qty: {existing['quantity']})")
                    break

            if not found_match:
                # Create new entry with unique key (name + rounded price)
                key = f"{name}_{int(price)}"
                deduplicated[key] = {
                    'name': name,
                    'size': product.get('size', ''),
                    'quantity': product.get('quantity', 1),
                    'price': Decimal(str(price)).quantize(Decimal('0.01')),
                    'seller': product.get('seller', 'H&M')
                }

        # Convert back to list
        final_products = list(deduplicated.values())
        print(
            f"[PARSER] After deduplication: {len(final_products)} unique product(s)")

        # If no products found, create a default one
        if not final_products:
            print(f"[PARSER] ⚠️  No products found, creating default")
            final_products.append({
                'name': 'H&M Product',
                'size': '',
                'quantity': 1,
                'price': Decimal('0'),
                'seller': 'H&M'
            })

        print("[PARSER] === Product Extraction Complete ===\n")
        return final_products

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
        """Extract total amount from H&M email (final total including shipping)"""
        text_content = soup.get_text()

        # H&M amount patterns (more specific to avoid picking up product prices)
        # Look for "Total" which is the final amount (Order value + Shipping)
        amount_patterns = [
            r'Total[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',  # Total: ₹1,047.00
            r'Amount[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',  # Amount: ₹1,047.00
            r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})\s*Total',      # ₹1,047.00 Total
        ]

        for pattern in amount_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = Decimal(amount_str).quantize(Decimal('0.01'))
                    # Validate it's a reasonable total (usually > 100 for orders)
                    if amount > 100:
                        return amount
                except:
                    continue

        # Fallback: Find largest price (likely the total)
        all_prices = re.findall(r'[₹$]\s*([0-9,]+\.?[0-9]{0,2})', text_content)
        if all_prices:
            try:
                prices = [Decimal(p.replace(',', '')).quantize(Decimal('0.01')) for p in all_prices]
                # Return the largest price that's > 100 (likely total)
                max_price = max([p for p in prices if p > 100], default=None)
                if max_price:
                    return max_price
            except:
                pass

        return None

    def extract_order_value(self, soup):
        """Extract Order value (sum of products) from H&M confirmation email"""
        text_content = soup.get_text()
        
        # Look for "Order value" followed by price (this is sum of products, before shipping)
        order_value_patterns = [
            r'Order\s+value[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',
            r'Subtotal[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',
            r'Items\s+total[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',
        ]
        
        for pattern in order_value_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                value_str = match.group(1).replace(',', '')
                try:
                    value = Decimal(value_str).quantize(Decimal('0.01'))
                    if value > 0:
                        return value
                except:
                    continue
        
        return None

    def extract_shipping_amount(self, soup):
        """Extract shipping & handling amount from H&M confirmation email"""
        text_content = soup.get_text()
        
        # Look for "Shipping & handling" or "Shipping" followed by price
        shipping_patterns = [
            r'Shipping\s*&\s*handling[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',
            r'Shipping[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',
            r'Delivery\s+charges?[:\s]+[₹$]?\s*([0-9,]+\.?[0-9]{0,2})',
        ]
        
        for pattern in shipping_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                shipping_str = match.group(1).replace(',', '')
                try:
                    shipping = Decimal(shipping_str).quantize(Decimal('0.01'))
                    if 0 < shipping < 10000:  # Reasonable shipping range
                        return shipping
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

    # H&M Strategy: Confirmation and delivery are different emails
    def parse_confirmation_email(self, soup):
        """H&M confirmation email - has individual prices + Order value + Shipping + Total"""
        print("\n[PARSER] === Parsing H&M Confirmation Email ===")
        
        products = self.extract_products(soup)
        
        # Extract amounts from confirmation email
        order_value = self.extract_order_value(soup)  # "Order value" (sum of products)
        shipping_amount = self.extract_shipping_amount(soup)  # "Shipping & handling"
        total_amount = self.extract_amount(soup)  # "Total" (Order value + Shipping)
        
        print(f"[PARSER] Order value: ₹{order_value if order_value else 'N/A'}")
        print(f"[PARSER] Shipping: ₹{shipping_amount if shipping_amount else 'N/A'}")
        print(f"[PARSER] Total: ₹{total_amount if total_amount else 'N/A'}")
        
        # If products don't have individual prices, distribute order_value
        products_with_prices = [p for p in products if p.get('price', 0) > 0]
        if len(products_with_prices) < len(products) and order_value:
            # Some products missing prices - distribute order_value
            print(f"[PARSER] Some products missing prices, distributing order_value")
            products = self.distribute_amount_to_products(products, order_value)
        
        # Store shipping in parsed_json
        parsed_json = {'source': 'html-hm-confirmation-v1'}
        if shipping_amount:
            parsed_json['shipping_amount'] = float(shipping_amount)
        if order_value:
            parsed_json['order_value'] = float(order_value)
        
        print("[PARSER] === Confirmation Email Parsing Complete ===\n")
        
        return {
            'merchant_name': 'H&M',
            'order_id': self.extract_order_id(soup),
            'order_date': self.extract_order_date(soup),
            'delivery_date': None,
            'return_deadline': None,
            'amount': total_amount,  # Total (Order value + Shipping)
            'shipping_amount': shipping_amount,  # New field
            'products': products,
            'tracking_number': None,
            'tracking_url': None,
            'email_type': 'confirmation',
            'confidence': 0.95,
            'parsed_json': parsed_json
        }

    def parse_shipping_email(self, soup):
        """H&M shipping email - same as delivery (single email strategy)"""
        return self.parse_delivery_email(soup)

    def parse_delivery_email(self, soup):
        """H&M delivery email - has individual prices, NO total amount"""
        print("\n[PARSER] === Parsing H&M Delivery Email ===")

        products = self.extract_products(soup)
        
        # Delivery emails have individual prices - DON'T distribute
        # Calculate total from sum of individual product prices
        total_amount = Decimal('0')
        for product in products:
            if product.get('price', 0) > 0:
                total_amount += Decimal(str(product['price']))
        
        print(f"[PARSER] Individual prices found: {len(products)} products")
        print(f"[PARSER] Calculated total from products: ₹{total_amount}")
        print("[PARSER] === Delivery Email Parsing Complete ===\n")

        return {
            'merchant_name': 'H&M',
            'order_id': self.extract_order_id(soup),
            'order_date': self.extract_order_date(soup),
            'delivery_date': None,  # Will be set from raw_email.received_at
            'return_deadline': self.extract_return_deadline(soup),
            'amount': total_amount,  # Sum of individual prices
            'products': products,
            'tracking_number': self.extract_tracking_number(soup),
            'tracking_url': self.extract_tracking_url(soup),
            'email_type': 'delivery',
            'confidence': 0.95,
            'parsed_json': {'source': 'html-hm-delivery-v1'}
        }
