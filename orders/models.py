from django.conf import settings
from django.db import models
from datetime import timedelta


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name='orders')

    raw_email = models.ForeignKey(
        'ingestion.RawEmail',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders'
    )
    merchant_name = models.CharField(max_length=100)
    # sometimes missing in emails
    order_id = models.CharField(max_length=100, blank=True)

    order_date = models.DateField()
    delivery_date = models.DateField(null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')

    return_window_days = models.IntegerField(default=30)
    return_deadline = models.DateField(null=True, blank=True)

    warranty_expiry = models.DateField(null=True, blank=True)

    parsed_confidence = models.FloatField(default=1.0)
    needs_review = models.BooleanField(default=False)

    parsed_json = models.JSONField(default=dict, blank=True)

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
        if self.delivery_date and self.return_window_days:
            return self.delivery_date + timedelta(days=self.return_window_days)
        return None

    def save(self, *args, **kwargs):
        # Always compute from current inputs; overwrites manual edits
        self.return_deadline = self.calculate_return_deadline()
        super().save(*args, **kwargs)
