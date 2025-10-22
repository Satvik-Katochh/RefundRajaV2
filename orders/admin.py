from django.contrib import admin
from django.apps import apps
from .models import Order, OrderProduct


class OrderProductInline(admin.TabularInline):
    """Inline admin for OrderProduct"""
    model = OrderProduct
    extra = 0
    fields = ('product_name', 'product_size', 'product_quantity', 'product_price',
              'seller_name', 'return_deadline', 'return_status')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant_name', 'order_id', 'user',
                    'order_date', 'delivery_date', 'total_amount', 'return_deadline', 'needs_review',)
    list_filter = ('merchant_name', 'needs_review', 'return_deadline')
    search_fields = ('order_id', 'merchant_name', 'user__username')
    list_select_related = ('user', 'raw_email')
    inlines = [OrderProductInline]

    def save_model(self, request, obj, form, change):
        # If user didn't change return_window_days explicitly, try to fill from MerchantRule
        if obj.merchant_name and (not change or 'return_window_days' not in form.changed_data):
            MerchantRule = apps.get_model('merchants', 'MerchantRule')
            rule = MerchantRule.objects.filter(
                merchant_name__iexact=obj.merchant_name).first()
            if rule:
                obj.return_window_days = rule.default_return_days
        super().save_model(request, obj, form, change)


@admin.register(OrderProduct)
class OrderProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_name', 'product_size', 'product_quantity',
                    'product_price', 'seller_name', 'return_status', 'return_deadline')
    list_filter = ('return_status', 'return_deadline', 'seller_name')
    search_fields = ('product_name', 'order__order_id', 'seller_name')
    list_select_related = ('order',)
    readonly_fields = ('created_at', 'updated_at',
                       'return_requested_at', 'returned_at')
