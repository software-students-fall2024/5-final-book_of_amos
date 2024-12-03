"""
A Flask application for predicting Rock-Paper-Scissors gestures using the Roboflow Inference API
and storing predictions in MongoDB.
"""

import os
import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError  # Specific exception for MongoDB
from inference_sdk import InferenceHTTPClient
from requests.exceptions import RequestException  # For handling request errors

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["rps_database"]
collection = db["predictions"]

# Roboflow Inference Client
API_URL = os.getenv("INFERENCE_SERVER_URL", "http://localhost:9001")
API_KEY = os.getenv("ROBOFLOW_API_KEY")  # API key passed via environment variables
MODEL_ID = os.getenv("ROBOFLOW_MODEL_ID")  # Model ID passed via environment variables
rf_client = InferenceHTTPClient(api_url=API_URL, api_key=API_KEY)


@app.route("/predict", methods=["POST"])
def predict():
    """
    Handle prediction requests.

    Accepts an image file, performs inference using the Roboflow model, and stores the result
    in MongoDB. Returns the predicted gesture and confidence score.
    """
    try:
        if "image" not in request.files:
            logging.error("No image file provided")
            return jsonify({"error": "No image file provided"}), 400

        # Save the uploaded image temporarily
        file = request.files["image"]
        image_path = f"./temp/{file.filename}"
        os.makedirs("./temp", exist_ok=True)
        file.save(image_path)

        # Perform inference using the Roboflow model
        result = rf_client.infer(image_path, model_id=MODEL_ID)

        # Extract prediction details
        prediction = result.get("predictions", [{}])[0]
        gesture = prediction.get("class", "Unknown")
        if gesture == "Unknown":
            prediction_score = 0
        else:
            prediction_score = prediction.get("confidence", 0)

        # Store prediction in MongoDB
        prediction_data = {
            "gesture": gesture,
            "prediction_score": prediction_score,
            "image_metadata": {"filename": file.filename},
        }
        collection.insert_one(prediction_data)
        logging.debug("Prediction data stored in MongoDB: %s", prediction_data)

        # Return the result
        return jsonify({"gesture": gesture, "confidence": prediction_score})
    except (RequestException, PyMongoError, FileNotFoundError) as prediction_error:
        logging.error("Prediction error: %s", str(prediction_error))
        return jsonify({"error": f"Prediction error: {str(prediction_error)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
