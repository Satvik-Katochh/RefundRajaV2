from rest_framework import viewsets, permissions
from .models import Order
from .serializers import OrderSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('user', 'raw_email').all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]  # keep simple for now
