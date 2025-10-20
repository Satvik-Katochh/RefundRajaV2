from rest_framework import serializers
from .models import RawEmail


class RawEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawEmail
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'user')
