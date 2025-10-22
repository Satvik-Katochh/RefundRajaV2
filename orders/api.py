from rest_framework import viewsets, permissions
from .models import Order, OrderProduct
from .serializers import OrderSerializer, OrderProductSerializer


class OrderViewSet(viewsets.ModelViewSet):
    """API viewset for Order model"""
    queryset = Order.objects.select_related(
        'user', 'raw_email').prefetch_related('products').all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only show orders belonging to the current user"""
        return Order.objects.filter(user=self.request.user).select_related('user', 'raw_email').prefetch_related('products')

    def perform_create(self, serializer):
        """Automatically set user to the authenticated user"""
        serializer.save(user=self.request.user)


class OrderProductViewSet(viewsets.ModelViewSet):
    """API viewset for OrderProduct model"""
    queryset = OrderProduct.objects.select_related('order').all()
    serializer_class = OrderProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only show products from orders belonging to the current user"""
        return OrderProduct.objects.filter(order__user=self.request.user).select_related('order')
