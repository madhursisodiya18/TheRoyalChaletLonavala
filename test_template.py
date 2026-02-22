from app import app, format_number
from flask import render_template_string, session

def test_format_number_in_template():
    # Create a simple template that uses the format_number filter
    template = """Price: ₹{{ price|int|format_number }}"""
    
    # Test with various numbers
    test_cases = [
        (1000, "Price: ₹1,000"),
        (1234567, "Price: ₹12,34,567"),
        (0, "Price: ₹0"),
        (999, "Price: ₹999"),
        (1000000, "Price: ₹10,00,000")
    ]
    
    # Create app context
    with app.app_context():
        for input_value, expected_output in test_cases:
            # Render the template with the test value
            result = render_template_string(template, price=input_value)
            print(f"Input: {input_value}, Expected: {expected_output}, Result: {result}")
            if result == expected_output:
                print(f"✅ Template test passed for {input_value}")
            else:
                print(f"❌ Template test failed for {input_value}. Expected: {expected_output}, Got: {result}")

if __name__ == "__main__":
    test_format_number_in_template()