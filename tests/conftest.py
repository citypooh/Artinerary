# In tests/conftest.py or at top of test file
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_gemini_api():
    """Mock Gemini API to speed up tests and prevent real network calls."""
    with patch("chatbot.ai_service.genai") as mock_genai:
        # Mock list_models to return a fake model
        mock_genai.list_models.return_value = [
            MagicMock(
                name="models/gemini-pro",
                supported_generation_methods=["generateContent"],
            )
        ]
        # Mock GenerativeModel and its generate_content method
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock(text="Mocked AI response")
        mock_genai.GenerativeModel.return_value = mock_model

        yield


@pytest.fixture(autouse=True)
def fast_ai_response():
    with patch(
        "chatbot.ai_service.ArtineraryAI._try_generate_with_fallback",
        return_value="Mocked AI response",
    ):
        yield


@pytest.fixture(autouse=True)
def fast_chatbot_mocks():
    from unittest.mock import patch, MagicMock

    requests_get_patcher = patch("requests.get")
    mock_get = requests_get_patcher.start()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "{}"
    mock_resp.json.return_value = {}
    mock_get.return_value = mock_resp

    sleep_patcher = patch("time.sleep", lambda *a, **k: None)
    sleep_patcher.start()

    yield

    requests_get_patcher.stop()
    sleep_patcher.stop()
