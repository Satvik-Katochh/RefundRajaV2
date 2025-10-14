from django.conf import settings
from django.db import models


class RawEmail(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name='raw_emails')
    message_id = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255, blank=True)
    from_email = models.CharField(max_length=255, blank=True)
    to_email = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField()

    raw_html = models.TextField(blank=True)
    raw_text = models.TextField(blank=True)

    # filenames/metadata for now
    attachments = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['message_id']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f'{self.subject or ""} [{self.message_id}]'
