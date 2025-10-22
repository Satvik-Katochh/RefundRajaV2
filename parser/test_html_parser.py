# parser/test_html_parser.py
from parser.html_parsers import MyntraHTMLParser


def test_myntra_parser():
    """Test Myntra HTML parser with sample HTML"""
    parser = MyntraHTMLParser()

    # Sample Myntra HTML (simplified version of your email)
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Myntra Order Delivered</title>
    </head>
    <body>
        <div>
            <span id="OrderDeliveredDateId">on Sun, 15 Jun</span>
            <span id="AvailableTillDateId">Sun, 22 Jun 2025</span>
            <p id="ItemProductBrandName">New Balance</p>
            <span id="ItemProductName">Printed Pure Cotton T-shirt</span>
            <span id="ItemSize">Size M</span>
            <span id="ItemQuantity">1</span>
            <div id="ItemSellerName">Sold by: Truecom Retail</div>
            <li id="OrderId">9725561686</li>
        </div>
    </body>
    </html>
    """

    result = parser.parse(sample_html)

    print("=== Myntra Parser Results ===")
    print(f"Merchant: {result['merchant_name']}")
    print(f"Order ID: {result['order_id']}")
    print(f"Order Date: {result['order_date']}")
    print(f"Delivery Date: {result['delivery_date']}")
    print(f"Return Deadline: {result['return_deadline']}")
    print(f"Return Window: {result['return_window_days']} days")
    print(f"Products: {len(result['products'])}")

    for i, product in enumerate(result['products'], 1):
        print(f"  Product {i}:")
        print(f"    Name: {product['name']}")
        print(f"    Size: {product['size']}")
        print(f"    Quantity: {product['quantity']}")
        print(f"    Seller: {product['seller']}")
        print(f"    Price: ₹{product['price']}")

    print(f"Confidence: {result['confidence']:.2f}")
    return result


if __name__ == "__main__":
    test_myntra_parser()
