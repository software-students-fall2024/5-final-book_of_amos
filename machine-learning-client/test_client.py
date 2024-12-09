"""Test module for Machine learning client"""

# test_client.py
# cd machine-learning-client
# pytest test_client.py -v
# pytest -v

# # python -m pytest --cov=client test_client.py

# pylint web-app/ machine-learning-client/
# pylint machine-learning-client/
# black .

import os
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest
from pymongo.errors import PyMongoError
from requests.exceptions import RequestException

sys.modules[
    "inference_sdk"
] = MagicMock()  # NEED!!! to mock the inference_sdk module before any local imports
from client import app  # pylint: disable=wrong-import-position


@pytest.fixture(name="flask_client")
def flask_client_fixture():
    """
    Provide a Flask test client for testing application routes.
    Yields:
        FlaskClient: A test client for the Flask application.
    """
    app.config["TESTING"] = True
    with app.test_client() as temp_client:
        yield temp_client


@pytest.fixture(name="mock_env_variables")
def mock_env_variables_fixture():
    """Mock environment variables for testing."""
    with patch.dict(
        os.environ,
        {
            "MONGO_URI": "mongodb://test:27017",
            "INFERENCE_SERVER_URL": "http://test:9001",
            "ROBOFLOW_API_KEY": "test_key",
            "ROBOFLOW_MODEL_ID": "test_model",
        },
    ):
        yield


@pytest.fixture(autouse=True)
def setup_directories():
    """Ensure temp directory exists"""
    os.makedirs("./temp", exist_ok=True)
    yield


@patch("client.rf_client")
@patch("client.collection")  # successful prediction test
def test_predict_success(mock_collection, mock_rf_client, flask_client):
    """Test successful predictions."""
    mock_rf_client.infer.return_value = {
        "predictions": [{"class": "Rock", "confidence": 0.95}]
    }
    mock_collection.insert_one.return_value = MagicMock()

    data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}
    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data=data
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["gesture"] == "Rock"
    assert json_data["confidence"] == 0.95
    mock_rf_client.infer.assert_called_once()
    mock_collection.insert_one.assert_called_once()


def test_predict_no_image(flask_client):
    """Test predictions with no image provided"""
    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data={}
    )
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["error"] == "No image file provided"


@patch("client.rf_client")
def test_predict_inference_failure(mock_rf_client, flask_client):
    """Test prediction with an inference failure"""
    mock_rf_client.infer.side_effect = RequestException("Inference API error")
    data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}

    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data=data
    )

    assert response.status_code == 500
    json_data = response.get_json()
    assert "Prediction error" in json_data["error"]


@patch("client.rf_client")
@patch("client.collection")
def test_predict_mongodb_failure(mock_collection, mock_rf_client, flask_client):
    """Test prediction with a database failure"""
    mock_rf_client.infer.return_value = {
        "predictions": [{"class": "Paper", "confidence": 0.85}]
    }
    mock_collection.insert_one.side_effect = PyMongoError("MongoDB insertion error")

    data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}
    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data=data
    )

    assert response.status_code == 500
    json_data = response.get_json()
    assert "Prediction error" in json_data["error"]


@patch("client.rf_client")
def test_predict_file_not_found(mock_rf_client, flask_client):
    """Test prediction with a file not found error"""
    mock_rf_client.infer.return_value = {
        "predictions": [{"class": "Scissors", "confidence": 0.90}]
    }

    with patch(
        "werkzeug.datastructures.FileStorage.save",
        side_effect=FileNotFoundError("File not found"),
    ):
        data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}
        response = flask_client.post(
            "/predict", content_type="multipart/form-data", data=data
        )

        assert response.status_code == 500
        json_data = response.get_json()
        assert "Prediction error" in json_data["error"]


@patch("client.rf_client")
@patch("client.collection")
def test_predict_unknown_gesture(mock_collection, mock_rf_client, flask_client):
    """Test prediction with unknown gesture"""
    mock_rf_client.infer.return_value = {
        "predictions": [{"class": "Unknown", "confidence": 0.5}]
    }
    mock_collection.insert_one.return_value = MagicMock()

    data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}
    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data=data
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["gesture"] == "Unknown"
    assert json_data["confidence"] == 0


@patch("client.rf_client")
@patch("client.collection")
def test_predict_missing_confidence(mock_collection, mock_rf_client, flask_client):
    """Test prediction with missing confidence in response"""
    mock_rf_client.infer.return_value = {"predictions": [{"class": "Rock"}]}
    mock_collection.insert_one.return_value = MagicMock()

    data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}
    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data=data
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["gesture"] == "Rock"
    assert json_data["confidence"] == 0


@patch("client.rf_client")
@patch("client.collection")
def test_predict_empty_predictions(mock_collection, mock_rf_client, flask_client):
    """Test prediction with empty predictions list"""
    mock_rf_client.infer.return_value = {"predictions": [{}]}
    mock_collection.insert_one.return_value = MagicMock()

    data = {"image": (BytesIO(b"fake image data"), "test_image.jpg")}
    response = flask_client.post(
        "/predict", content_type="multipart/form-data", data=data
    )

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["gesture"] == "Unknown"
    assert json_data["confidence"] == 0
