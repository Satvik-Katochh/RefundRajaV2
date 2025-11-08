# parser/services/order_merger.py
from orders.models import Order, OrderProduct
from decimal import Decimal
from django.db import models


class OrderMerger:
    """Handles merging of multiple emails into complete orders"""

    def create_or_update_order(self, user, parsed_data, raw_email=None):
        """Create new order or update existing one"""
        order_id = parsed_data.get('order_id')
        email_type = parsed_data.get('email_type')
        merchant_name = parsed_data.get('merchant_name')

        if not order_id or not merchant_name:
            return None

        # Try to find existing order
        # For shipping emails, we might need to match by other criteria
        existing_order = Order.objects.filter(
            user=user,
            merchant_name__iexact=merchant_name
        ).filter(
            # Try multiple matching strategies
            models.Q(order_id=order_id) |  # Direct order ID match
            # Tracking number match
            models.Q(parsed_json__tracking__tracking_number=order_id)
        ).first()

        if existing_order:
            return self.update_order_from_email(existing_order, parsed_data, email_type)
        else:
            return self.create_new_order_from_email(user, parsed_data, raw_email)

    def create_new_order_from_email(self, user, parsed_data, raw_email=None):
        """Create new order from email data"""
        # Only create if we have minimum required data
        if not parsed_data.get('merchant_name'):
            return None

        # For shipping emails, we might not have order_date, use shipping_date as fallback
        # For delivery emails, we might not have order_date, use delivery_date as fallback
        order_date = parsed_data.get(
            'order_date') or parsed_data.get('shipping_date') or parsed_data.get('delivery_date')
        if not order_date:
            return None

        # Create Order
        order = Order(
            user=user,
            raw_email=raw_email,
            merchant_name=parsed_data['merchant_name'],
            order_id=parsed_data.get('order_id', ''),
            order_date=order_date,  # Use fallback order_date
            delivery_date=parsed_data.get(
                'delivery_date') or parsed_data.get('estimated_delivery'),
            currency=parsed_data.get('currency', 'INR'),
            return_window_days=parsed_data.get('return_window_days', 30),
            parsed_confidence=parsed_data.get(
                'parsed_confidence', parsed_data.get('confidence', 0.0)),
            needs_review=parsed_data.get(
                'parsed_confidence', parsed_data.get('confidence', 0.0)) < 0.7,
            parsed_json=parsed_data.get('parsed_json', {}),
            total_amount=parsed_data.get(
                'amount', Decimal('0.00'))  # Set initial amount
        )
        # Store tracking information for shipping and delivery emails
        if parsed_data.get('email_type') in ['shipping', 'delivery']:
            tracking_info = {}
            if parsed_data.get('tracking_number'):
                tracking_info['tracking_number'] = parsed_data['tracking_number']
            if parsed_data.get('logistics_partner'):
                tracking_info['logistics_partner'] = parsed_data['logistics_partner']
            if parsed_data.get('tracking_url'):
                tracking_info['tracking_url'] = parsed_data['tracking_url']
            if parsed_data.get('shipping_date'):
                tracking_info['shipping_date'] = str(
                    parsed_data['shipping_date'])
            if parsed_data.get('estimated_delivery'):
                tracking_info['estimated_delivery'] = str(
                    parsed_data['estimated_delivery'])

            if tracking_info:
                order.parsed_json['tracking'] = tracking_info

        order.save()  # This will auto-calculate return_deadline

        # Create OrderProduct(s)
        products = parsed_data.get('products', [])
        
        print(f"\n[ORDER] === Creating OrderProducts ===")
        print(f"[ORDER] Received {len(products)} product(s) from parser")
        
        if not products:
            # Single product fallback - create from old structure
            print(f"[ORDER] No products in parsed_data, using fallback")
            products = [{
                'name': parsed_data.get('product_name', 'Unknown Product'),
                'size': parsed_data.get('product_size', ''),
                'quantity': parsed_data.get('product_quantity', 1),
                'price': parsed_data.get('amount', 0),
                'seller': parsed_data.get('seller_name', '')
            }]

        # Final deduplication check before creating OrderProducts
        # Group by name + size + price (within ₹1 tolerance)
        unique_products = {}
        for product_data in products:
            name = product_data['name']
            size = product_data.get('size', '')
            price = float(product_data.get('price', 0))
            
            # Create key: name + size
            key = f"{name}|{size}"
            
            if key in unique_products:
                # Merge: sum quantities, keep higher price
                existing = unique_products[key]
                existing['quantity'] = existing.get('quantity', 1) + product_data.get('quantity', 1)
                if price > float(existing.get('price', 0)):
                    existing['price'] = Decimal(str(price)).quantize(Decimal('0.01'))
                print(f"[ORDER] Merged duplicate product: {name[:40]}... (total qty: {existing['quantity']})")
            else:
                unique_products[key] = {
                    'name': name,
                    'size': size,
                    'quantity': product_data.get('quantity', 1),
                    'price': Decimal(str(price)).quantize(Decimal('0.01')),
                    'seller': product_data.get('seller', 'H&M')
                }
        
        print(f"[ORDER] After deduplication: {len(unique_products)} unique product(s)")

        # Create OrderProduct for each unique product
        created_count = 0
        for idx, (key, product_data) in enumerate(unique_products.items(), 1):
            print(f"[ORDER] Product {idx}/{len(unique_products)}: {product_data['name'][:40]}... (₹{product_data.get('price', 0)}, Qty: {product_data.get('quantity', 1)})")
            
            # Check if this product already exists for this order (safety check)
            existing_product = OrderProduct.objects.filter(
                order=order,
                product_name=product_data['name'],
                product_size=product_data.get('size', '')
            ).first()
            
            if existing_product:
                # Update quantity if product already exists
                existing_product.product_quantity += product_data.get('quantity', 1)
                if float(product_data.get('price', 0)) > float(existing_product.product_price):
                    existing_product.product_price = product_data['price']
                existing_product.save()
                print(f"[ORDER] Updated existing product (qty: {existing_product.product_quantity})")
            else:
                # Create new OrderProduct
                OrderProduct.objects.create(
                    order=order,
                    product_name=product_data['name'],
                    product_size=product_data.get('size', ''),
                    product_quantity=product_data.get('quantity', 1),
                    product_price=product_data['price'],
                    seller_name=product_data.get('seller', ''),
                    return_deadline=order.return_deadline
                )
                created_count += 1
        
        print(f"[ORDER] ✓ Created {created_count} new OrderProduct(s), updated {len(unique_products) - created_count} existing")
        print(f"[ORDER] === OrderProduct Creation Complete ===\n")

        return order

    def update_order_from_email(self, order, parsed_data, email_type):
        """Update existing order with new email data"""
        if email_type == "confirmation":
            # Update price and order date
            # Confirmation email has the correct total (includes shipping)
            if parsed_data.get('amount'):
                order.total_amount = parsed_data['amount']
            if parsed_data.get('order_date'):
                order.order_date = parsed_data['order_date']
            
            # Store shipping amount in parsed_json if available
            if parsed_data.get('shipping_amount'):
                if 'shipping_amount' not in order.parsed_json:
                    order.parsed_json['shipping_amount'] = float(parsed_data['shipping_amount'])

            # Update products with prices
            self.update_products_with_prices(
                order, parsed_data.get('products', []))

        elif email_type == "delivery":
            # Update delivery date and return deadline
            if parsed_data.get('delivery_date'):
                order.delivery_date = parsed_data['delivery_date']
            if parsed_data.get('return_deadline'):
                order.return_deadline = parsed_data['return_deadline']

            # Don't overwrite total_amount if confirmation email already set it (with shipping)
            # Delivery email amount is just sum of products (no shipping)
            # Only update if total_amount is 0 or not set
            if parsed_data.get('amount') and (not order.total_amount or order.total_amount == 0):
                order.total_amount = parsed_data['amount']

            # Store tracking information for delivery emails (H&M strategy)
            if parsed_data.get('tracking_number') or parsed_data.get('tracking_url'):
                tracking_info = order.parsed_json.get('tracking', {})
                if parsed_data.get('tracking_number'):
                    tracking_info['tracking_number'] = parsed_data['tracking_number']
                if parsed_data.get('tracking_url'):
                    tracking_info['tracking_url'] = parsed_data['tracking_url']
                order.parsed_json['tracking'] = tracking_info

            # Update product return deadlines
            self.update_product_return_deadlines(order)

        elif email_type == "shipping":
            # Update tracking info and estimated delivery
            if parsed_data.get('tracking_number'):
                tracking_info = order.parsed_json.get('tracking', {})
                tracking_info['tracking_number'] = parsed_data['tracking_number']
                order.parsed_json['tracking'] = tracking_info

            if parsed_data.get('estimated_delivery'):
                tracking_info = order.parsed_json.get('tracking', {})
                tracking_info['estimated_delivery'] = str(
                    parsed_data['estimated_delivery'])
                order.parsed_json['tracking'] = tracking_info
                # Also update delivery_date if not set
                if not order.delivery_date:
                    order.delivery_date = parsed_data['estimated_delivery']

            if parsed_data.get('logistics_partner'):
                tracking_info = order.parsed_json.get('tracking', {})
                tracking_info['logistics_partner'] = parsed_data['logistics_partner']
                order.parsed_json['tracking'] = tracking_info

            if parsed_data.get('tracking_url'):
                tracking_info = order.parsed_json.get('tracking', {})
                tracking_info['tracking_url'] = parsed_data['tracking_url']
                order.parsed_json['tracking'] = tracking_info

            if parsed_data.get('shipping_date'):
                tracking_info = order.parsed_json.get('tracking', {})
                tracking_info['shipping_date'] = str(
                    parsed_data['shipping_date'])
                order.parsed_json['tracking'] = tracking_info

        # Update confidence score
        new_confidence = parsed_data.get(
            'confidence', parsed_data.get('parsed_confidence', 0.0))
        if new_confidence > order.parsed_confidence:
            order.parsed_confidence = new_confidence
            order.needs_review = new_confidence < 0.7

        order.save()
        return order

    def update_products_with_prices(self, order, products_data):
        """Update products with price information"""
        for product_data in products_data:
            # Try to find existing product by name
            product = order.products.filter(
                product_name=product_data['name']
            ).first()

            if product and product_data.get('price'):
                product.product_price = product_data['price']
                product.save()
            elif not product and product_data.get('name'):
                # Create new product if it doesn't exist
                OrderProduct.objects.create(
                    order=order,
                    product_name=product_data['name'],
                    product_size=product_data.get('size', ''),
                    product_quantity=product_data.get('quantity', 1),
                    product_price=product_data.get('price', 0),
                    seller_name=product_data.get('seller', ''),
                    return_deadline=order.return_deadline
                )

    def update_product_return_deadlines(self, order):
        """Update all products with order's return deadline"""
        for product in order.products.all():
            product.return_deadline = order.return_deadline
            product.save()
