from rest_framework import serializers
from .models import Order, OrderProduct


class OrderProductSerializer(serializers.ModelSerializer):
    """Serializer for OrderProduct model"""
    can_return = serializers.ReadOnlyField()

    class Meta:
        model = OrderProduct
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at',
                            'return_requested_at', 'returned_at')


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model with nested products"""
    products = OrderProductSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    return_status = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at',
                            'return_deadline', 'total_amount')
