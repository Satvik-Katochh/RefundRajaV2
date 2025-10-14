from django.contrib import admin
from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant_name', 'order_id', 'user',
                    'order_date', 'delivery_date', 'return_deadline', 'needs_review')
    list_filter = ('merchant_name', 'needs_review', 'return_deadline')
    search_fields = ('order_id', 'merchant_name', 'user__username')
