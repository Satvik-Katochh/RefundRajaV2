from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from datetime import timedelta


class Order(models.Model):
    """
    Main order model - represents a single order that can contain multiple products
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name='orders')

    raw_email = models.ForeignKey(
        'ingestion.RawEmail',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders'
    )

    # Order-level information
    merchant_name = models.CharField(max_length=100)
    # sometimes missing in emails
    order_id = models.CharField(max_length=100, blank=True)

    # Dates
    order_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)

    # Financial information (calculated from products)
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='INR')

    # Return policy (default for all products in this order)
    return_window_days = models.IntegerField(default=30)
    # Calculated from delivery_date + return_window_days
    return_deadline = models.DateField(null=True, blank=True)

    # Warranty information
    warranty_expiry = models.DateField(null=True, blank=True)

    # Parsing and review information
    parsed_confidence = models.FloatField(default=1.0)
    needs_review = models.BooleanField(default=False)
    parsed_json = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['return_deadline']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.merchant_name} {self.order_id or ""} ({self.user_id})'.strip()

    def calculate_return_deadline(self):
        """Calculate return deadline based on delivery date and return window"""
        if self.delivery_date and self.return_window_days:
            return self.delivery_date + timedelta(days=self.return_window_days)
        return None

    def calculate_total_amount(self):
        """Calculate total amount from all products"""
        return sum(product.product_price * product.product_quantity for product in self.products.all())

    def get_return_status(self):
        """Get overall return status of the order"""
        products = self.products.all()
        if not products.exists():
            return 'no_products'

        returned_count = products.filter(return_status='returned').count()
        total_count = products.count()

        if returned_count == 0:
            return 'none_returned'
        elif returned_count == total_count:
            return 'fully_returned'
        else:
            return 'partially_returned'

    def save(self, *args, **kwargs):
        # Always compute return deadline from current inputs
        self.return_deadline = self.calculate_return_deadline()
        super().save(*args, **kwargs)


class OrderProduct(models.Model):
    """
    Individual products within an order
    Supports partial returns - each product can be returned independently
    """
    RETURN_STATUS_CHOICES = [
        ('not_returned', 'Not Returned'),
        ('return_requested', 'Return Requested'),
        ('returned', 'Returned'),
        ('return_rejected', 'Return Rejected'),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='products')

    # Product details
    product_name = models.CharField(max_length=300)
    product_size = models.CharField(max_length=50, blank=True)
    product_quantity = models.IntegerField(default=1)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Seller information
    seller_name = models.CharField(max_length=200, blank=True)

    # Return tracking (individual per product)
    # Can be different from order deadline
    return_deadline = models.DateField(null=True, blank=True)
    return_status = models.CharField(
        max_length=20, choices=RETURN_STATUS_CHOICES, default='not_returned')
    return_requested_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True)  # Why user wants to return

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['return_deadline']),
            models.Index(fields=['return_status']),
        ]
        ordering = ['created_at']

    def __str__(self):
        return f'{self.product_name} (Order: {self.order.order_id})'

    def calculate_return_deadline(self):
        """Calculate return deadline for this specific product"""
        if self.return_deadline:
            return self.return_deadline
        elif self.order.delivery_date and self.order.return_window_days:
            return self.order.delivery_date + timedelta(days=self.order.return_window_days)
        return None

    def can_return(self):
        """Check if this product can still be returned"""
        if self.return_status in ['returned', 'return_rejected']:
            return False

        deadline = self.calculate_return_deadline()
        if deadline:
            return timezone.now().date() <= deadline
        return False

    def request_return(self, reason=''):
        """Mark this product as requested for return"""
        if self.can_return():
            self.return_status = 'return_requested'
            self.return_reason = reason
            self.return_requested_at = timezone.now()
            self.save()
            return True
        return False

    def mark_returned(self):
        """Mark this product as successfully returned"""
        if self.return_status == 'return_requested':
            self.return_status = 'returned'
            self.returned_at = timezone.now()
            self.save()
            return True
        return False

    def save(self, *args, **kwargs):
        # Auto-calculate return deadline if not set
        if not self.return_deadline:
            self.return_deadline = self.calculate_return_deadline()
        super().save(*args, **kwargs)


# Signal handlers to automatically update order total when products change
@receiver(post_save, sender=OrderProduct)
def update_order_total_on_product_save(sender, instance, **kwargs):
    """Update order total when a product is saved"""
    order = instance.order
    order.total_amount = order.calculate_total_amount()
    order.save(update_fields=['total_amount'])


@receiver(post_delete, sender=OrderProduct)
def update_order_total_on_product_delete(sender, instance, **kwargs):
    """Update order total when a product is deleted"""
    order = instance.order
    order.total_amount = order.calculate_total_amount()
    order.save(update_fields=['total_amount'])
