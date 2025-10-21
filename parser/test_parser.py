# parser/test_parser.py
from services import parse_email

# Sample Flipkart email
sample_email = """
Subject: Your Flipkart Order Has Shipped
From: noreply@flipkart.com

Dear Customer,

Order #OD12345 placed on 01 Oct 2025.
Delivered on 10 Oct 2025.
Amount ₹899.00.

Thank you for shopping with Flipkart!
"""

# Test the parser
result = parse_email(sample_email, "noreply@flipkart.com")
print("Parsed Result:")
for key, value in result.items():
    print(f"  {key}: {value}")
