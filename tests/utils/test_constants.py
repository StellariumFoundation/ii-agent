import unittest

# Import the constants from the module
from src.ii_agent.utils import constants

class TestConstants(unittest.TestCase):

    def test_upload_folder_name(self):
        self.assertTrue(hasattr(constants, "UPLOAD_FOLDER_NAME"), "UPLOAD_FOLDER_NAME constant is missing.")
        self.assertIsInstance(constants.UPLOAD_FOLDER_NAME, str, "UPLOAD_FOLDER_NAME should be a string.")
        self.assertEqual(constants.UPLOAD_FOLDER_NAME, "uploaded_files")

    def test_complete_message(self):
        self.assertTrue(hasattr(constants, "COMPLETE_MESSAGE"), "COMPLETE_MESSAGE constant is missing.")
        self.assertIsInstance(constants.COMPLETE_MESSAGE, str, "COMPLETE_MESSAGE should be a string.")
        self.assertEqual(constants.COMPLETE_MESSAGE, "Completed the task.")

    def test_default_model(self):
        self.assertTrue(hasattr(constants, "DEFAULT_MODEL"), "DEFAULT_MODEL constant is missing.")
        self.assertIsInstance(constants.DEFAULT_MODEL, str, "DEFAULT_MODEL should be a string.")
        self.assertEqual(constants.DEFAULT_MODEL, "claude-sonnet-4@20250514")

if __name__ == "__main__":
    unittest.main()
