from rest_framework import viewsets, permissions
from .models import RawEmail
from .serializers import RawEmailSerializer


class RawEmailViewSet(viewsets.ModelViewSet):
    queryset = RawEmail.objects.all()
    serializer_class = RawEmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show emails belonging to the current user
        return RawEmail.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically set user to the authenticated user
        serializer.save(user=self.request.user)
