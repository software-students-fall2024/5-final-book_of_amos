import eventlet

eventlet.monkey_patch()
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, disconnect, join_room
from uuid import uuid4
import random
from threading import Lock
import os
import time
import random
from flask import Flask, render_template, request, jsonify, make_response
import requests
from requests.exceptions import RequestException
from pymongo import MongoClient
from bson.objectid import ObjectId

# Initialize Flask and Socket.IO
app = Flask(__name__, template_folder="templates", static_folder="static")
socketio = SocketIO(app)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["rps_database"]
collection = db["stats"]

# In-memory data
waiting_players = []
active_games = {}
matchmaking_lock = Lock()
player_stats = {"wins": 0, "losses": 0, "ties": 0}
# ----------- ROUTES -----------


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
    for attempt in range(retries):
        try:
            # Reset file pointers for retries
            for file in files.values():
                file.stream.seek(0)
            response = requests.post(url, files=files, timeout=timeout)
            response.raise_for_status()
            return response
        except RequestException as error:
            logging.warning("Retry attempt %d failed: %s", attempt + 1, str(error))
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                logging.error("All retry attempts failed.")
                return None
    return None


@app.route("/result", methods=["POST"])
def result():
    try:
        if "image" not in request.files:
            app.logger.error("No image file provided")
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        if not file or not file.filename:
            app.logger.error("Invalid file in request")
            return jsonify({"error": "Invalid file provided"}), 400

        ml_client_url = os.getenv(
            "ML_CLIENT_URL", "http://machine-learning-client:5000"
        )
        response = retry_request(
            f"{ml_client_url}/predict", files={"image": file}, timeout=20
        )

        if not response:
            app.logger.error("ML client did not respond")
            return jsonify({"error": "ML client did not respond"}), 500

        result = response.json()
        if not result or "gesture" not in result:
            app.logger.error("Invalid response from ML client: %s", result)
            return jsonify({"error": "Invalid response from ML client"}), 500

        user_gesture = result.get("gesture", "Unknown").lower()
        ai_gesture = random.choice(["rock", "paper", "scissors"])
        game_result = determine_winners(user_gesture, ai_gesture)

        return jsonify(
            {
                "user_gesture": user_gesture,
                "ai_choice": ai_gesture,
                "result": game_result,
            }
        )
    except Exception as e:
        app.logger.error(f"Error processing the result: {e}")
        return jsonify({"error": f"Error processing the result: {e}"}), 500


def determine_winners(user, ai_choice):
    """
    Determine the winner of the Rock-Paper-scissors game.

    Args:
        user (str): User's gesture.
        ai_choice (str): AI's gesture.

    Returns:
        str: Result of the game.
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


# ----------- ai_image -----------
@app.route("/play/ai", methods=["POST"])
def play_against_ai():
    """
    Handle the game logic for playing against AI.
    """
    data = request.json
    player_name = data.get("player_name", "Player")
    player_choice = data.get("choice")

    if player_choice not in ["rock", "paper", "scissors"]:
        return jsonify({"error": "Invalid choice"}), 400
    ai_choice = random.choice(["rock", "paper", "scissors"])
    result = determine_ai_winner(player_choice, ai_choice)
    update_player_stats(result)

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
    """
    outcomes = {
        "rock": {"rock": "tie", "paper": "lose", "scissors": "win"},
        "paper": {"rock": "win", "paper": "tie", "scissors": "lose"},
        "scissors": {"rock": "lose", "paper": "win", "scissors": "tie"},
    }
    return outcomes[player_choice][ai_choice]


def update_player_stats(result):
    """
    Update the player's stats based on the result of the game.
    """
    if result == "win":
        player_stats["wins"] += 1
    elif result == "lose":
        player_stats["losses"] += 1
    elif result == "tie":
        player_stats["ties"] += 1


# ----------- MATCHMAKING -----------
@socketio.on("random_match")
def handle_random_match(data):
    player_name = data.get("player_name")
    player_id = data.get("player_id")
    sid = request.sid

    if not player_name or not player_id:
        emit("error", {"message": "Player name and ID are required."})
        return

    with matchmaking_lock:
        if waiting_players:
            # Match found
            opponent = waiting_players.pop(0)
            game_id = str(uuid4())
            active_games[game_id] = {
                "player1_id": opponent["player_id"],
                "player2_id": player_id,
                "player1_sid": opponent["sid"],
                "player2_sid": sid,
                "player1_name": opponent["player_name"],
                "player2_name": player_name,
                "ready": {"player1": False, "player2": False},
            }

            # Notify both players about the match
            emit(
                "match_found",
                {"game_id": game_id, "opponent": opponent["player_name"]},
                to=sid,
            )
            emit(
                "match_found",
                {"game_id": game_id, "opponent": player_name},
                to=opponent["sid"],
            )

            # Start the countdown
            socketio.start_background_task(countdown_timer, game_id)
        else:
            # Add the player to the waiting queue
            waiting_players.append(
                {"player_id": player_id, "player_name": player_name, "sid": sid}
            )
            emit("waiting", {"message": "Waiting for an opponent..."}, to=sid)


@socketio.on("cancel_waiting")
def handle_cancel_waiting(data):
    """Handle player canceling waiting for a match."""
    player_id = data.get("player_id")
    sid = request.sid

    with matchmaking_lock:
        # Find and remove the player from the waiting queue
        for player in waiting_players:
            if player["player_id"] == player_id and player["sid"] == sid:
                waiting_players.remove(player)
                break

    # Notify the player that the waiting has been canceled
    emit("waiting_cancelled", {"message": "You canceled waiting for an opponent."})


@socketio.on("cancel_match")
def handle_cancel_match(data):
    """Handle a player canceling the match."""
    game_id = data.get("game_id")
    player_id = data.get("player_id")

    if not game_id or not player_id:
        emit("error", {"message": "Game ID and Player ID are required."})
        return

    # Fetch the game from active games
    game = active_games.pop(game_id, None)
    if game:
        # Determine who canceled the match
        canceling_player = (
            game["player1_name"]
            if game["player1_id"] == player_id
            else game["player2_name"]
        )

        # Notify all players in the room about the cancellation
        socketio.emit(
            "match_cancelled",
            {"message": f"Match canceled by {canceling_player}."},
            room=game_id,
        )

    # Ensure all game states are cleared after cancellation
    reset_game_state(game_id)


def countdown_timer(game_id):
    """Countdown timer for players to start the game."""
    game = active_games.get(game_id)
    if not game:
        return  # Exit if the game no longer exists

    for remaining in range(10, -1, -1):
        socketio.sleep(1)  # Emit countdown every second
        socketio.emit(
            "countdown", {"game_id": game_id, "countdown": remaining}, room=game_id
        )

        # Stop countdown if both players are ready
        game = active_games.get(game_id)  # Re-fetch to ensure game is still valid
        if game and all(game["ready"].values()):
            return

    # Cancel match if players aren't ready
    game = active_games.pop(game_id, None)
    if game:
        socketio.emit(
            "match_cancelled",
            {"message": "Match canceled due to timeout."},
            room=game_id,
        )
        reset_game_state(game_id)


def reset_game_state(game_id):
    """Reset game-related states for a clean slate."""
    if game_id in active_games:
        del active_games[game_id]


@socketio.on("start_game")
def handle_start_game(data):
    """Handle a player clicking 'Start Game'."""
    game_id = data.get("game_id")
    player_id = data.get("player_id")
    sid = request.sid

    # Validate game ID and player ID
    if not game_id or not player_id:
        emit("error", {"message": "Game ID and Player ID are required."})
        return

    # Fetch the game
    game = active_games.get(game_id)
    if not game:
        emit("error", {"message": "Invalid game ID."})
        return

    # Update player's readiness and ensure they are in the room
    if player_id == game["player1_id"]:
        game["player1_sid"] = sid  # Update session ID
        join_room(game_id)
        game["ready"]["player1"] = True

    elif player_id == game["player2_id"]:
        game["player2_sid"] = sid  # Update session ID
        join_room(game_id)
        game["ready"]["player2"] = True

    else:
        emit("error", {"message": "Invalid player ID."})
        return

    # Check if both players are ready
    if all(game["ready"].values()):
        socketio.emit(
            "proceed_to_game",
            {"message": "Both players are ready! Starting the game..."},
            room=game_id,
        )


@socketio.on("join_game")
def handle_join_game(data):
    game_id = data.get("game_id")
    player_id = data.get("player_id")

    if not game_id or not player_id:
        emit("error", {"message": "Game ID and Player ID are required."})
        return

    game = active_games.get(game_id)
    if not game:
        emit("error", {"message": "Invalid game ID."})
        return

    sid = request.sid

    if player_id == game["player1_id"]:
        game["player1_sid"] = sid
    elif player_id == game["player2_id"]:
        game["player2_sid"] = sid
    else:
        emit("error", {"message": "You are not part of this game."})
        return

    join_room(game_id)

    # Notify both players about readiness and ensure the game starts
    socketio.emit("start_game", {"message": "Game starting soon!"}, room=game_id)


# ----------- GAMEPLAY -----------
@socketio.on("submit_choice")
def handle_submit_choice(data):
    """Handle a player's choice submission."""
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

    # Check if both players have made their choices
    if game["player1_choice"] and game["player2_choice"]:
        print(
            f"Choices: {game['player1_choice']}, {game['player2_choice']}"
        )  # Debugging
        result = determine_winner(
            game["player1_choice"],
            game["player2_choice"],
            game["player1_name"],
            game["player2_name"],
        )

        # Send the result to both players in the game room
        socketio.emit(
            "game_result",
            {
                "player1_name": game["player1_name"],
                "player2_name": game["player2_name"],
                "player1_choice": game["player1_choice"],
                "player2_choice": game["player2_choice"],
                "result": result,
            },
            room=game_id,
        )

        # Reset the game
        reset_game(game_id)


def reset_game(game_id):
    """Reset the game state."""
    if game_id in active_games:
        active_games[game_id]["player1_choice"] = None
        active_games[game_id]["player2_choice"] = None


def determine_winner(player1_choice, player2_choice, player1_name, player2_name):
    """Determine the winner for a multiplayer game."""
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


@socketio.on("disconnect")
def handle_disconnect():
    """Handle player disconnection."""
    sid = request.sid
    for game_id, game in list(active_games.items()):
        if game["player1_sid"] == sid:
            game["player1_sid"] = None
        elif game["player2_sid"] == sid:
            game["player2_sid"] = None

        # Clean up the game if both players are disconnected
        if not game["player1_sid"] and not game["player2_sid"]:
            del active_games[game_id]


# ----------- START THE SERVER -----------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=True)
