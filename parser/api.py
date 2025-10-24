
from ingestion.models import RawEmail
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
# Import directly from services.py file to avoid circular import with services/ package
import importlib.util
import os
spec = importlib.util.spec_from_file_location(
    "parser_services", os.path.join(os.path.dirname(__file__), "services.py"))
parser_services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser_services)


class ParserViewSet(viewsets.ViewSet):
    """
    Parser API endpoints
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='parse-and-create-order')
    def parse_and_create_order(self, request):
        """
        Parse email text and create order
        """
        # Get data from request
        raw_text = request.data.get('raw_text')
        raw_html = request.data.get('raw_html')
        from_email = request.data.get('from_email')
        subject = request.data.get('subject', 'Parsed Email')

        # Validate required fields
        if not raw_text and not raw_html:
            return Response(
                {'error': 'Either raw_text or raw_html is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Step 1: Parse the email
            parsed_data = parser_services.parse_email(
                raw_text, from_email=from_email, raw_html=raw_html)

            # Step 2: Check if we have minimum required data
            if not parsed_data.get('merchant_name') or not parsed_data.get('order_date'):
                return Response(
                    {
                        'error': 'Could not extract merchant_name or order_date from email',
                        'parsed_data': parsed_data
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 3: Create RawEmail record
            raw_email = RawEmail.objects.create(
                user=request.user,
                message_id=f"api-{request.user.id}-{hash(str(raw_text or raw_html)) % 10000}",
                subject=subject,
                from_email=from_email,
                to_email=request.user.email,
                received_at='2025-01-15 10:00:00',
                raw_text=raw_text or '',
                raw_html=raw_html or ''
            )

            # Step 4: Create Order from parsed data
            order = parser_services.create_order_from_email(
                raw_email, parsed_data)

            if order:
                return Response(
                    {
                        'success': True,
                        'order_id': order.id,
                        'merchant_name': order.merchant_name,
                        'order_date': order.order_date,
                        'delivery_date': order.delivery_date,
                        'total_amount': str(order.total_amount),
                        'return_deadline': order.return_deadline,
                        'needs_review': order.needs_review,
                        'parsed_confidence': order.parsed_confidence,
                        'products_count': order.products.count(),
                        'parsed_data': parsed_data
                    },
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    {
                        'error': 'Failed to create order - missing required data',
                        'parsed_data': parsed_data
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            return Response(
                {
                    'error': f'Parsing failed: {str(e)}',
                    'raw_text': raw_text,
                    'from_email': from_email
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
