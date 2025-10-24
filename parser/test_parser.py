# parser/test_parser.py
import importlib.util
import os
spec = importlib.util.spec_from_file_location(
    "parser_services", os.path.join(os.path.dirname(__file__), "services.py"))
parser_services = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser_services)

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
result = parser_services.parse_email(sample_email, "noreply@flipkart.com")
print("Parsed Result:")
for key, value in result.items():
    print(f"  {key}: {value}")
