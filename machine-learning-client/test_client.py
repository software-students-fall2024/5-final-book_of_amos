"""Test module for Machine learning client"""

# test_client.py
# cd machine-learning-client
# pytest test_client.py -v
# pytest -v

# pylint web-app/ machine-learning-client/
# black .


import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
import mongomock

# Fixture to mock MongoClient before importing client.py
@pytest.fixture
def mock_mongo(monkeypatch):
    """
    Mock MongoClient using mongomock and patch it in the client module.
    """
    mock_client = mongomock.MongoClient()
    # Patch 'MongoClient' in 'client' module with mongomock's MongoClient
    monkeypatch.setattr("client.MongoClient", lambda uri: mock_client)
    return mock_client

# Fixture to mock rf_client.infer before importing client.py
@pytest.fixture
def mock_rf_infer(monkeypatch):
    """
    Mock the 'infer' method of the Roboflow Inference Client.
    """
    mock_infer = MagicMock()
    monkeypatch.setattr("client.rf_client.infer", mock_infer)
    return mock_infer

# Fixture to import app and provide test client after mocks
@pytest.fixture
def app_client(mock_mongo, mock_rf_infer):
    """
    Import the Flask app after mocking dependencies and provide a test client.
    """
    from client import app  # Import after mocks are applied
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client, mock_mongo, mock_infer

# Test the /predict route successfully
def test_predict_success(app_client):
    client, mock_mongo_client, mock_infer = app_client
    # Set the return value for rf_client.infer
    mock_infer.return_value = {
        "predictions": [{"class": "rock", "confidence": 0.95}]
    }

    data = {
        "image": (BytesIO(b"fake image data"), "test_image.jpg")
    }

    response = client.post("/predict", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["gesture"] == "rock"
    assert json_data["confidence"] == 0.95

    # Verify that the prediction was stored in MongoDB
    mock_db = mock_mongo_client["rps_database"]["predictions"]
    prediction = mock_db.find_one({"gesture": "rock"})
    assert prediction is not None
    assert prediction["prediction_score"] == 0.95
    assert prediction["image_metadata"]["filename"] == "test_image.jpg"

# Test the /predict route with no image provided
def test_predict_no_image(app_client):
    client, _, _ = app_client
    response = client.post("/predict", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["error"] == "No image file provided"

# Test the /predict route with inference failure
def test_predict_inference_failure(app_client):
    client, _, mock_infer = app_client
    # Set 'rf_client.infer' to raise an exception
    mock_infer.side_effect = Exception("Inference API error")

    data = {
        "image": (BytesIO(b"fake image data"), "test_image.jpg")
    }

    response = client.post("/predict", data=data, content_type="multipart/form-data")
    assert response.status_code == 500
    json_data = response.get_json()
    assert "Prediction error" in json_data["error"]
    assert "Inference API error" in json_data["error"]

# Test the /predict route with MongoDB insertion failure
def test_predict_mongodb_failure(app_client):
    client, mock_mongo_client, mock_infer = app_client
    # Set 'rf_client.infer' to return valid data
    mock_infer.return_value = {
        "predictions": [{"class": "paper", "confidence": 0.85}]
    }

    # Patch 'collection.insert_one' to raise an exception
    with patch("client.collection.insert_one", side_effect=Exception("MongoDB insertion error")):
        data = {
            "image": (BytesIO(b"fake image data"), "test_image.jpg")
        }

        response = client.post("/predict", data=data, content_type="multipart/form-data")
        assert response.status_code == 500
        json_data = response.get_json()
        assert "Prediction error" in json_data["error"]
        assert "MongoDB insertion error" in json_data["error"]

# Test the /predict route with invalid inference response (missing 'class' key)
def test_predict_invalid_inference_response(app_client):
    client, mock_mongo_client, mock_infer = app_client
    # Set 'rf_client.infer' to return predictions without 'class'
    mock_infer.return_value = {"predictions": [{"confidence": 0.80}]}  # Missing 'class'

    data = {
        "image": (BytesIO(b"fake image data"), "test_image.jpg")
    }

    response = client.post("/predict", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["gesture"] == "Unknown"
    assert json_data["confidence"] == 0

# Test the /predict route with FileNotFoundError during file saving
def test_predict_file_not_found(app_client):
    client, mock_mongo_client, mock_infer = app_client
    # Patch 'FileStorage.save' to raise FileNotFoundError
    with patch("werkzeug.datastructures.FileStorage.save", side_effect=FileNotFoundError("File not found")):
        data = {
            "image": (BytesIO(b"fake image data"), "test_image.jpg")
        }

        response = client.post("/predict", data=data, content_type="multipart/form-data")
        assert response.status_code == 500
        json_data = response.get_json()
        assert "Prediction error" in json_data["error"]
        assert "File not found" in json_data["error"]

