from app import app, format_number

def test_format_number_filter():
    # Test with various numbers
    test_cases = [
        (1000, '1,000'),  # Basic case
        (1234567, '12,34,567'),  # Indian format
        (0, '0'),  # Zero
        (999, '999'),  # Below 1000
        (1000000, '10,00,000')  # Million
    ]
    
    # Create app context
    with app.app_context():
        for input_value, expected_output in test_cases:
            result = format_number(input_value)
            print(f"Input: {input_value}, Expected: {expected_output}, Result: {result}")
            if result == expected_output:
                print(f"✅ Format number test passed for {input_value}")
            else:
                print(f"❌ Format number test failed for {input_value}. Expected: {expected_output}, Got: {result}")

if __name__ == "__main__":
    test_format_number_filter()