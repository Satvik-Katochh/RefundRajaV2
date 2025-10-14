from django.db import models


class MerchantRule(models.Model):
    merchant_name = models.CharField(max_length=100, unique=True)
    default_return_days = models.IntegerField(default=30)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['merchant_name']
        indexes = [
            models.Index(fields=['merchant_name']),
        ]

    def __str__(self):
        return f'{self.merchant_name} ({self.default_return_days} days)'
