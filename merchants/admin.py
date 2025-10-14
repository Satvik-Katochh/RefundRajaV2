from django.contrib import admin
from .models import MerchantRule


@admin.register(MerchantRule)
class MerchantRuleAdmin(admin.ModelAdmin):
    list_display = ('merchant_name', 'default_return_days')
    search_fields = ('merchant_name',)
