
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

    @action(detail=False, methods=['post'], url_path='sync-gmail')
    def sync_gmail(self, request):
        """
        Sync emails from Gmail and process them
        """
        print(f"\n[API] sync_gmail - User: {request.user.username}")

        user = request.user
        max_results = request.data.get('max_results', 3)

        try:
            # Step 1: Initialize GmailService
            from parser.gmail_service import GmailService
            gmail_service = GmailService(user)

            # Step 2: Fetch emails from Gmail
            email_data_list = gmail_service.fetch_emails(
                max_results=max_results)

            # Step 3: Process each email
            results = []
            print(f"[API] Processing {len(email_data_list)} email(s)")

            for idx, email_data in enumerate(email_data_list, 1):
                print(
                    f"[API] Email {idx}/{len(email_data_list)}: {email_data['subject'][:40]}...")
                result = self._process_single_email(user, email_data)
                results.append(result)
                result_status = result.get('status', 'unknown')
                order_id = result.get('order_id')
                print(f"[API] Email {idx} -> {result_status}" +
                      (f" (Order ID: {order_id})" if order_id else ""))

            return Response({
                'success': True,
                'emails_processed': len(results),
                'orders_created': sum(1 for r in results if r.get('order_id')),
                'results': results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _process_single_email(self, user, email_data):
        """
        Process a single email: create RawEmail → parse → create Order
        """
        from ingestion.models import RawEmail

        print(f"\n>>> Email Processing Started <<<")
        print(f"[API] Subject: {email_data['subject'][:60]}...")
        print(f"[API] From: {email_data['from_email']}")
        print(
            f"[API] HTML Length: {len(email_data.get('raw_html', ''))} chars")
        print(
            f"[API] Text Length: {len(email_data.get('raw_text', ''))} chars")

        try:
            # Step 1: Create RawEmail record (check for duplicates first)
            print(f"[API] Step 1: Creating RawEmail record...")

            # Check if this email was already processed
            existing_raw_email = RawEmail.objects.filter(
                user=user,
                message_id=email_data['id']
            ).first()

            if existing_raw_email:
                print(
                    f"[API] ⚠️  RawEmail already exists (ID: {existing_raw_email.id}), skipping duplicate")
                # Still parse and create order in case it wasn't processed before
                raw_email = existing_raw_email
            else:
                raw_email = RawEmail.objects.create(
                    user=user,
                    message_id=email_data['id'],
                    subject=email_data['subject'],
                    from_email=email_data['from_email'],
                    to_email=user.email,
                    received_at=email_data['received_at'],
                    raw_html=email_data['raw_html'],
                    raw_text=email_data['raw_text']
                )
                print(f"[API] ✓ RawEmail created (ID: {raw_email.id})")

            # Step 2: Parse email using existing parser
            print(f"[API] Step 2: Parsing email...")
            parsed_data = parser_services.parse_email(
                raw_text=email_data['raw_text'],
                raw_html=email_data['raw_html'],
                from_email=email_data['from_email']
            )
            print(f"[API] ✓ Parsing complete")
            print(f"[API]   - Merchant: {parsed_data.get('merchant_name')}")
            print(
                f"[API]   - Products: {len(parsed_data.get('products', []))}")

            # Step 2.5: Fix delivery_date for delivery emails
            if parsed_data.get('email_type') == 'delivery' and not parsed_data.get('delivery_date'):
                if raw_email and raw_email.received_at:
                    parsed_data['delivery_date'] = raw_email.received_at.date()
                    print(f"[API] Using email received_at as delivery_date: {parsed_data['delivery_date']}")

            # Step 3: Create Order from parsed data
            print(f"[API] Step 3: Creating Order...")
            order = parser_services.create_order_from_email(
                raw_email, parsed_data
            )

            if order:
                print(f"[API] ✓ Order created (ID: {order.id})")
            else:
                print(f"[API] ✗ Order creation failed")

            print(f"<<< Email Processing Complete <<<\n")

            return {
                'email_id': email_data['id'],
                'order_id': order.id if order else None,
                'merchant': parsed_data.get('merchant_name'),
                'status': 'success' if order else 'failed'
            }

        except Exception as e:
            print(f"[API] ✗ ERROR: {str(e)}")
            print(f"<<< Email Processing Failed <<<\n")
            return {
                'email_id': email_data.get('id', 'unknown'),
                'order_id': None,
                'merchant': None,
                'status': 'error',
                'error': str(e)
            }
