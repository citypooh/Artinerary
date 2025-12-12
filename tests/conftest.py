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

        mock_response = MagicMock()
        mock_response.text = "Mocked AI response"
        mock_genai.GenerativeModel.return_value.generate_content.return_value = (
            mock_response
        )

        yield mock_genai


@pytest.fixture(autouse=True)
def fast_ai_response():
    with patch(
        "chatbot.ai_service.ArtineraryAI._try_generate_with_fallback",
        return_value="Mocked AI response",
    ):
        yield


@pytest.fixture(autouse=True)
def fast_chatbot_mocks():
    """
    Autouse fixture to speed up chatbot-related tests by mocking slow/external ops:
    - mocks requests.get to return a simple empty response
    - no-ops time.sleep
    Adjust or narrow the patch targets if some tests depend on real external responses.
    """
    # Patch requests.get used by ai_service / other modules
    requests_get_patcher = patch("requests.get")
    mock_get = requests_get_patcher.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "{}"
    mock_resp.json.return_value = {}
    mock_get.return_value = mock_resp

    # No-op time.sleep to eliminate artificial delays
    sleep_patcher = patch("time.sleep", lambda *a, **k: None)
    sleep_patcher.start()

    yield

    # stop patchers
    requests_get_patcher.stop()
    sleep_patcher.stop()
