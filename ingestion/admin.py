from django.contrib import admin
from .models import RawEmail


@admin.register(RawEmail)
class RawEmailAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'from_email',
                    'received_at', 'message_id')
    search_fields = ('message_id', 'subject', 'from_email',
                     'to_email', 'user__username')
    list_filter = ('received_at',)
