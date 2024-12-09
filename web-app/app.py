"""Main application file for Rock-Paper-Scissors game using Flask and Socket.IO."""

import os
import time
import random
import logging
from threading import Lock

# from uuid import uuid4

import eventlet
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from pymongo import MongoClient
from requests.exceptions import RequestException

# Apply monkey patching
eventlet.monkey_patch()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)

# Initialize Flask and Socket.IO
app = Flask(__name__, template_folder="templates", static_folder="static")
socketio = SocketIO(app)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
CLIENT = MongoClient(MONGO_URI)
DB = CLIENT["rps_database"]
COLLECTION = DB["stats"]

# In-memory data
waiting_players = []
active_games = {}
MATCHMAKING_LOCK = Lock()
player_stats = {"wins": 0, "losses": 0, "ties": 0}

# ----------- ROUTES -----------

# pylint: disable=redefined-outer-name


@app.route("/")
def home():
    """Render the home page."""
    return render_template("home.html")


@app.route("/ai")
def ai_page():
    """Render the AI game page."""
    return render_template("ai.html")


@app.route("/ai_machine_learning")
def ai_ml_page():
    """Render the AI Machine Learning game page."""
    return render_template("ai_machine_learning.html")


@app.route("/real_person")
def real_person_page():
    """Render the real person game page."""
    return render_template("real_person.html")


def retry_request(url, files, retries=5, delay=2, timeout=10):
    """
    Retry a POST request with exponential backoff.

    Args:
        url (str): The URL to send the request to.
        files (dict): The files to include in the request.
        retries (int): The number of retry attempts.
        delay (int): The delay between retries.
        timeout (int): The request timeout.

    Returns:
        Response: The successful response or None if all retries failed.
    """
    for attempt in range(retries):
        try:
            for file in files.values():
                file.stream.seek(0)
            response = requests.post(url, files=files, timeout=timeout)
            response.raise_for_status()
            return response
        except RequestException as error:
            LOGGER.warning("Retry attempt %d failed: %s",
                           attempt + 1, str(error))
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                LOGGER.error("All retry attempts failed.")
    return None


@app.route("/result", methods=["POST"])
def result():
    """
    Handle result endpoint for processing game results.

    Returns:
        JSON response with the game result.
    """
    try:
        if "image" not in request.files:
            LOGGER.error("No image file provided")
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        if not file or not file.filename:
            LOGGER.error("Invalid file in request")
            return jsonify({"error": "Invalid file provided"}), 400

        ml_client_url = os.getenv(
            "ML_CLIENT_URL", "http://machine-learning-client:5000"
        )
        response = retry_request(
            f"{ml_client_url}/predict", files={"image": file}, timeout=20
        )

        if not response:
            LOGGER.error("ML client did not respond")
            return jsonify({"error": "ML client did not respond"}), 500

        result_data = response.json()
        if not result_data or "gesture" not in result_data:
            LOGGER.error("Invalid response from ML client: %s", result_data)
            return jsonify({"error": "Invalid response from ML client"}), 500

        user_gesture = result_data.get("gesture", "Unknown").lower()
        ai_gesture = random.choice(["rock", "paper", "scissors"])
        game_result = determine_winners(user_gesture, ai_gesture)

        return jsonify(
            {
                "user_gesture": user_gesture,
                "ai_choice": ai_gesture,
                "result": game_result,
            }
        )
    except KeyError as key_err:
        LOGGER.error("KeyError processing the result: %s", key_err)
        return jsonify({"error": f"Missing or invalid key: {key_err}"}), 400
    except ValueError as val_err:
        LOGGER.error("ValueError processing the result: %s", val_err)
        return jsonify({"error": f"Invalid value: {val_err}"}), 400
    except RequestException as req_err:
        LOGGER.error("RequestException processing the result: %s", req_err)
        return jsonify({"error": "Error communicating with the ML client"}), 500


def determine_winners(user, ai_choice):
    """
    Determine the winner of the Rock-Paper-Scissors game.

    Args:
        user (str): The user's gesture.
        ai_choice (str): The AI's gesture.

    Returns:
        str: The result of the game.
    """
    winning_cases = {
        "rock": "scissors",
        "paper": "rock",
        "scissors": "paper",
    }

    if user == ai_choice:
        return "It's a tie!"
    if ai_choice == winning_cases.get(user):
        return "You win!"
    return "AI wins!"


@app.route("/play/ai", methods=["POST"])
def play_against_ai():
    """
    Handle the game logic for playing against AI.

    Returns:
        JSON response with the game result and updated stats.
    """
    data = request.json
    player_name = data.get("player_name", "Player")
    player_choice = data.get("choice")

    if player_choice not in ["rock", "paper", "scissors"]:
        return jsonify({"error": "Invalid choice"}), 400
    ai_choice = random.choice(["rock", "paper", "scissors"])
    new_result = determine_ai_winner(player_choice, ai_choice)
    update_player_stats(new_result)

    return jsonify(
        {
            "player_name": player_name,
            "player_choice": player_choice,
            "ai_choice": ai_choice,
            "result": result,
            "stats": player_stats,
        }
    )


def determine_ai_winner(player_choice, ai_choice):
    """
    Determine the winner for AI games.

    Args:
        player_choice (str): The player's choice.
        ai_choice (str): The AI's choice.

    Returns:
        str: The result of the game.
    """
    outcomes = {
        "rock": {"rock": "tie", "paper": "lose", "scissors": "win"},
        "paper": {"rock": "win", "paper": "tie", "scissors": "lose"},
        "scissors": {"rock": "lose", "paper": "win", "scissors": "tie"},
    }
    return outcomes[player_choice][ai_choice]


def update_player_stats(new_result):
    """
    Update the player's stats based on the result of the game.

    Args:
        result (str): The result of the game ("win", "lose", or "tie").
    """
    if new_result == "win":
        player_stats["wins"] += 1
    elif new_result == "lose":
        player_stats["losses"] += 1
    elif new_result == "tie":
        player_stats["ties"] += 1


# ----------- MATCHMAKING AND GAME MANAGEMENT -----------


@socketio.on("disconnect")
def handle_disconnect():
    """
    Handle a player's disconnection.

    Removes the player from the game or matchmaking queue.
    """
    sid = request.sid
    for game_id, game in list(active_games.items()):
        if game["player1_sid"] == sid:
            game["player1_sid"] = None
        elif game["player2_sid"] == sid:
            game["player2_sid"] = None

        if not game["player1_sid"] and not game["player2_sid"]:
            del active_games[game_id]


@socketio.on("submit_choice")
def handle_submit_choice(data):
    """
    Handle a player's choice submission.

    Args:
        data (dict): Contains game ID, player ID, and choice.
    """
    game_id = data.get("game_id")
    player_id = data.get("player_id")
    choice = data.get("choice")

    if game_id not in active_games:
        emit("error", {"message": "Invalid game ID."})
        return

    game = active_games[game_id]

    if player_id == game["player1_id"]:
        game["player1_choice"] = choice
    elif player_id == game["player2_id"]:
        game["player2_choice"] = choice
    else:
        emit("error", {"message": "Invalid player ID."})
        return

    if game.get("player1_choice") and game.get("player2_choice"):
        new_result = determine_winner(
            game["player1_choice"],
            game["player2_choice"],
            game["player1_name"],
            game["player2_name"],
        )
        socketio.emit(
            "game_result",
            {
                "player1_name": game["player1_name"],
                "player2_name": game["player2_name"],
                "player1_choice": game["player1_choice"],
                "player2_choice": game["player2_choice"],
                "result": new_result,
            },
            room=game_id,
        )
        reset_game(game_id)


def reset_game(game_id):
    """
    Reset the game state for the given game ID.

    Args:
        game_id (str): The ID of the game to reset.
    """
    if game_id in active_games:
        active_games[game_id]["player1_choice"] = None
        active_games[game_id]["player2_choice"] = None


def determine_winner(player1_choice, player2_choice, player1_name, player2_name):
    """
    Determine the winner for a multiplayer game.

    Args:
        player1_choice (str): Player 1's choice.
        player2_choice (str): Player 2's choice.
        player1_name (str): Player 1's name.
        player2_name (str): Player 2's name.

    Returns:
        str: The result of the game.
    """
    outcomes = {
        "rock": {
            "rock": "tie",
            "paper": f"{player2_name} wins!",
            "scissors": f"{player1_name} wins!",
        },
        "paper": {
            "rock": f"{player1_name} wins!",
            "paper": "tie",
            "scissors": f"{player2_name} wins!",
        },
        "scissors": {
            "rock": f"{player2_name} wins!",
            "paper": f"{player1_name} wins!",
            "scissors": "tie",
        },
    }
    return outcomes[player1_choice][player2_choice]


# ----------- MAIN -----------

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=True)
