import unittest

class TestUserData(unittest.TestCase):
    def test_generate_user_data(self):
        """
        Simulates the generation of user data and checks if it matches expected values.
        """
        from my_module import generate_user_data  # Import the function to be tested

        # Simulated user data
        user_data = {
            "name": "Nicole Freeman",
            "email": "nicole.freeman@example.com",
            "city": "Wells",
            "country": "United Kingdom"
        }

        # Expected user data
        expected_user_data = {
            "name": "Nicole Freeman",
            "email": "nicole.freeman@example.com",
            "city": "Wells",
            "country": "United Kingdom"
        }

        # Generate user data using the function to be tested
        actual_user_data = generate_user_data()

        # Assert that the generated user data matches the expected user data
        self.assertEqual(actual_user_data, expected_user_data)

if __name__ == '__main__':
    unittest.main()
