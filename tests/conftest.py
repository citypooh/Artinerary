# In tests/conftest.py or at top of test file
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_gemini_api():
    """Mock Gemini API to speed up tests"""
    with patch("chatbot.ai_service.genai") as mock_genai:
        mock_model = MagicMock()
        mock_model.name = "models/gemini-2.0-flash"
        mock_model.supported_generation_methods = ["generateContent"]
        mock_genai.list_models.return_value = [mock_model]
        mock_genai.GenerativeModel.return_value = MagicMock()
        yield mock_genai
