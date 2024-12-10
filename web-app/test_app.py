"""
Unit tests for the Flask application defined in `app.py`.
"""

# test_app.py
# cd web-app
# pytest test_app.py -v  # DONT USE THIS/ USE BELOW WITH VENV
# python -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt

# python -m pytest test_app.py -v
# python -m pytest --cov=app test_app.py

# pylint web-app/
# pylint web-app/test_app.py
# pylint test_app.py
# black .

from app import (
    app,
    socketio,
    determine_winners,
    determine_ai_winner,
    retry_request,
    active_games,
    waiting_players,
    player_stats,
    countdown_timer,
    handle_disconnect,
)
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from flask_socketio import SocketIOTestClient
from requests.exceptions import RequestException
from bson.objectid import ObjectId
from uuid import uuid4

# this mocks the eventlet module
import sys

eventlet_mock = MagicMock()
eventlet_mock.monkey_patch = MagicMock()
sys.modules["eventlet"] = eventlet_mock


@pytest.fixture
def client():
    """Flask test client"""
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def socket_client():
    """Socket.IO test client"""
    return SocketIOTestClient(app, socketio)


@pytest.fixture
def mock_mongodb(monkeypatch):
    """Mock MongoDB client using mongomock."""
    import mongomock

    # Create a mock MongoDB client
    mock_client = mongomock.MongoClient()

    # Replace the `collection` in the app with the mock collection
    monkeypatch.setattr("app.collection", mock_client["test"]["stats"])

    return mock_client


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Reset game state before each test"""
    active_games.clear()
    waiting_players.clear()
    player_stats.update({"wins": 0, "losses": 0, "ties": 0})
    yield


# testing HTTP Routes
def test_home_page(client, mock_mongodb):
    """Test the home page route."""
    response = client.get("/")
    assert response.status_code == 200


def test_ai_page(client):
    """Test the AI game page route"""
    response = client.get("/ai")
    assert response.status_code == 200


def test_ai_ml_page(client):
    """Test the AI ML game page route"""
    response = client.get("/ai_machine_learning")
    assert response.status_code == 200


def test_real_person_page(client):
    """Test the real person game page route"""
    response = client.get("/real_person")
    assert response.status_code == 200


# Test Game Logic
def test_determine_winners():
    """Test the determine_winners function"""
    assert determine_winners("rock", "scissors") == "You win!"
    assert determine_winners("rock", "paper") == "AI wins!"
    assert determine_winners("rock", "rock") == "It's a tie!"


def test_determine_ai_winner():
    """Test the determine_ai_winner function"""
    assert determine_ai_winner("rock", "scissors") == "win"
    assert determine_ai_winner("rock", "paper") == "lose"
    assert determine_ai_winner("rock", "rock") == "tie"


# def test_update_player_stats(mock_mongodb):
#     """Test the update_player_stats function."""
#     from app import update_player_stats, player_stats

#     # Reset player stats
#     player_stats["wins"] = 0
#     player_stats["losses"] = 0
#     player_stats["ties"] = 0

#     # Generate a valid ObjectId
#     valid_id = str(ObjectId())

#     # Insert a mock document into the mock database
#     mock_mongodb["test"]["stats"].insert_one({"_id": ObjectId(valid_id)})

#     # Test updates
#     update_player_stats("win", "rock", valid_id)
#     assert player_stats["wins"] == 1


# # Testing AI Play Route
# def test_play_against_ai_valid(client, mock_mongodb):
#     """Test playing against AI with valid input."""
#     # Set the required cookie
#     client.set_cookie("db_object_id", "test_id")

#     # Make the request
#     response = client.post(
#         "/play/ai", json={"player_name": "Test Player", "choice": "rock"}
#     )

#     # Assert the response
#     assert response.status_code == 200
#     data = response.get_json()
#     assert data["player_name"] == "Test Player"
#     assert data["player_choice"] == "rock"
#     assert data["ai_choice"] in ["rock", "paper", "scissors"]
#     assert data["result"] in ["win", "lose", "tie"]
#     assert all(key in data["stats"] for key in ["wins", "losses", "ties"])


def test_play_against_ai_invalid(client):
    """Test playing against AI with invalid input"""
    response = client.post(
        "/play/ai", json={"player_name": "Test", "choice": "invalid"}
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Invalid choice"


# # Test Result Route
# @patch("app.retry_request")
# def test_result_endpoint_success(mock_retry, client, mock_mongodb):
#     """Test the result endpoint with successful ML client response."""
#     # Set the required cookie
#     client.set_cookie("db_object_id", "test_id")

#     # Mock the ML client response
#     mock_response = MagicMock()
#     mock_response.json.return_value = {"gesture": "rock"}
#     mock_response.status_code = 200
#     mock_retry.return_value = mock_response

#     # Prepare test data
#     data = {"image": (BytesIO(b"test image data"), "test.jpg")}

#     # Send the POST request
#     response = client.post("/result", data=data,
#                            content_type="multipart/form-data")

#     # Assert the response
#     assert response.status_code == 200
#     result = response.get_json()
#     assert result["user_gesture"] == "rock"
#     assert result["ai_choice"] in ["rock", "paper", "scissors"]
#     assert result["result"] in ["It's a tie!", "You win!", "AI wins!"]


def test_result_endpoint_no_image(client):
    """Test the result endpoint with no image"""
    response = client.post("/result", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    result = json.loads(response.data)
    assert "error" in result
    assert result["error"] == "No image file provided"


def test_result_endpoint_empty_file(client):
    """Test the result endpoint with empty file"""
    data = {"image": (BytesIO(b""), "")}
    response = client.post("/result", data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    result = json.loads(response.data)
    assert "error" in result
    assert result["error"] == "Invalid file provided"


@patch("app.retry_request")
def test_result_endpoint_ml_failure(mock_retry, client, mock_mongodb):
    """Test the result endpoint when ML client fails."""
    # Set the required cookie
    client.set_cookie("db_object_id", "test_id")

    # Mock the ML client to simulate failure
    mock_retry.return_value = None

    # Prepare test data
    data = {"image": (BytesIO(b"test image data"), "test.jpg")}

    # Send the POST request
    response = client.post("/result", data=data, content_type="multipart/form-data")

    # Assert the response
    assert response.status_code == 500
    result = response.get_json()
    assert "error" in result
    assert result["error"] == "ML client did not respond"


@patch("requests.post")
def test_retry_request_function(mock_post):
    """Test retry_request function"""
    mock_files = {"image": MagicMock()}
    mock_files["image"].stream = BytesIO(b"test")

    # Test successful request
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    result = retry_request("http://test.com/predict", mock_files)
    assert result == mock_response
    mock_post.assert_called_once_with(
        "http://test.com/predict", files=mock_files, timeout=10
    )

    # Reset mock
    mock_post.reset_mock()

    # Test failed request with retries
    mock_post.side_effect = [RequestException("Test error")] * 3
    result = retry_request("http://test.com/predict", mock_files, retries=3, delay=0)
    assert result is None
    assert mock_post.call_count == 3  # Initial try + 2 retries


def test_random_match_invalid_data(socket_client):  # socket.IO tests here
    """Test random match with invalid data"""
    socket_client.emit("random_match", {})
    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"
    assert "required" in received[0]["args"][0]["message"].lower()


def test_random_match_missing_name(socket_client):
    """Test random match with missing name"""
    socket_client.emit("random_match", {"player_id": "123"})
    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"


def test_random_match_missing_id(socket_client):
    """Test random match with missing ID"""
    socket_client.emit("random_match", {"player_name": "Player1"})
    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"


def test_cancel_match(socket_client):
    """Test canceling a match"""
    game_id = "test_game"
    player_id = "123"
    active_games[game_id] = {
        "player1_id": player_id,
        "player2_id": "456",
        "player1_name": "Player1",
        "player2_name": "Player2",
    }

    socket_client.emit("cancel_match", {"game_id": game_id, "player_id": player_id})

    assert game_id not in active_games


def test_cancel_match_invalid_data(socket_client):
    """Test canceling a match with invalid data"""
    socket_client.emit("cancel_match", {})
    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"


def test_join_game_success(socket_client):
    """Test joining a game successfully"""
    game_id = "test_game"
    player_id = "123"
    active_games[game_id] = {
        "player1_id": player_id,
        "player2_id": "456",
        "player1_name": "Player1",
        "player2_name": "Player2",
    }

    socket_client.emit("join_game", {"game_id": game_id, "player_id": player_id})

    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "start_game"


def test_join_game_invalid_game(socket_client):
    """Test joining an invalid game"""
    socket_client.emit("join_game", {"game_id": "invalid_game", "player_id": "123"})

    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"
    assert "Invalid game ID" in received[0]["args"][0]["message"]


def test_join_game_invalid_player(socket_client):
    """Test joining with invalid player"""
    game_id = "test_game"
    active_games[game_id] = {"player1_id": "123", "player2_id": "456"}

    socket_client.emit("join_game", {"game_id": game_id, "player_id": "invalid_player"})

    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"
    assert "not part of this game" in received[0]["args"][0]["message"]


def test_submit_choice_invalid_game(socket_client):
    """Test submitting choice for invalid game"""
    socket_client.emit(
        "submit_choice",
        {"game_id": "invalid_game", "player_id": "123", "choice": "rock"},
    )

    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "error"
    assert "Invalid game ID" in received[0]["args"][0]["message"]


def test_reset_game():
    """Test game reset functionality"""
    from app import reset_game

    game_id = "test_game"
    active_games[game_id] = {"player1_choice": "rock", "player2_choice": "paper"}

    reset_game(game_id)
    assert active_games[game_id]["player1_choice"] is None
    assert active_games[game_id]["player2_choice"] is None


def test_random_match_first_player(socket_client):
    """Test first player joining random match"""
    socket_client.emit("random_match", {"player_name": "Player1", "player_id": "123"})
    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "waiting"
    assert len(waiting_players) == 1
    assert waiting_players[0]["player_name"] == "Player1"


def test_random_match_second_player(socket_client):
    """Test second player joining and getting matched"""
    # Add first player to waiting list
    waiting_players.append(
        {"player_id": "123", "player_name": "Player1", "sid": "test_sid_1"}
    )

    socket_client.emit(
        "random_match", {"player_name": "Player2", "player_id": "456"}  # second player
    )

    received = socket_client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "match_found"
    assert len(waiting_players) == 0
    assert len(active_games) == 1


def test_cancel_waiting(socket_client):
    """Test canceling wait for match"""
    # Add player to waiting list
    player_id = "123"
    socket_client.emit(
        "random_match", {"player_name": "Player1", "player_id": player_id}
    )
    socket_client.get_received()  # Clear received messages

    socket_client.emit("cancel_waiting", {"player_id": player_id})  # waiting
    received = socket_client.get_received()

    assert len(received) == 1
    assert received[0]["name"] == "waiting_cancelled"
    assert len(waiting_players) == 0


def test_start_game(socket_client):
    """Test starting a game"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_name": "Player1",
        "player2_name": "Player2",
        "ready": {"player1": False, "player2": False},
    }
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "123"})
    assert active_games[game_id]["ready"]["player1"] == True


def test_submit_choice(socket_client):
    """Test submitting a game choice"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_name": "Player1",
        "player2_name": "Player2",
        "player1_choice": None,
        "player2_choice": None,
    }

    socket_client.emit(
        "submit_choice", {"game_id": game_id, "player_id": "123", "choice": "rock"}
    )
    assert active_games[game_id]["player1_choice"] == "rock"


def test_countdown_timer():
    """Test countdown timer function"""
    from app import countdown_timer

    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "ready": {"player1": False, "player2": False},
    }

    with patch("app.socketio.emit") as mock_emit:
        countdown_timer(game_id)
        assert game_id not in active_games
        assert mock_emit.called


def test_handle_cancel_match_missing_data(socket_client):
    """Test canceling match with missing data"""
    socket_client.emit("cancel_match", {"game_id": "test_game"})  # Missing player_id
    received = socket_client.get_received()
    assert received[0]["name"] == "error"
    assert "required" in received[0]["args"][0]["message"].lower()


def test_start_game_missing_data(socket_client):
    """Test starting game with missing data"""
    socket_client.emit("start_game", {"game_id": "test_game"})  # Missing player_id
    received = socket_client.get_received()
    assert received[0]["name"] == "error"
    assert "required" in received[0]["args"][0]["message"].lower()


def test_join_game_missing_data(socket_client):
    """Test joining game with missing data"""
    socket_client.emit("join_game", {"game_id": "test_game"})  # Missing player_id
    received = socket_client.get_received()
    assert received[0]["name"] == "error"
    assert "required" in received[0]["args"][0]["message"].lower()


def test_determine_winner_all_combinations():
    """Test all possible combinations in determine_winner function"""
    from app import determine_winner

    test_cases = [
        ("rock", "scissors", "Player1", "Player2", "Player1 wins!"),
        ("rock", "paper", "Player1", "Player2", "Player2 wins!"),
        ("rock", "rock", "Player1", "Player2", "tie"),
        ("paper", "rock", "Player1", "Player2", "Player1 wins!"),
        ("paper", "scissors", "Player1", "Player2", "Player2 wins!"),
        ("paper", "paper", "Player1", "Player2", "tie"),
        ("scissors", "paper", "Player1", "Player2", "Player1 wins!"),
        ("scissors", "rock", "Player1", "Player2", "Player2 wins!"),
        ("scissors", "scissors", "Player1", "Player2", "tie"),
    ]
    for p1_choice, p2_choice, p1_name, p2_name, expected in test_cases:
        result = determine_winner(p1_choice, p2_choice, p1_name, p2_name)
        assert result == expected


def test_reset_game_state():
    """Test reset_game_state function"""
    from app import reset_game_state

    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "ready": {"player1": True, "player2": True},
    }
    reset_game_state(game_id)
    assert game_id not in active_games


def test_result_endpoint_invalid_ml_response(client):
    """Test handling invalid ML client response"""
    with patch("app.retry_request") as mock_retry:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "invalid": "response"
        }  # Missing required fields
        mock_retry.return_value = mock_response

        data = {"image": (BytesIO(b"test image data"), "test.jpg")}
        response = client.post("/result", data=data)
        assert response.status_code == 500


# Fix 1: Update test_update_player_stats
def test_update_player_stats(mock_mongodb):
    """Test the update_player_stats function."""
    from app import update_player_stats

    # Create a valid document structure
    valid_id = str(ObjectId())
    initial_stats = {
        "rock": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "paper": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "scissors": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "totals": {"wins": 0, "losses": 0, "ties": 0},
    }

    # Insert the document with proper structure
    mock_mongodb["test"]["stats"].insert_one(
        {"_id": ObjectId(valid_id), **initial_stats}
    )

    # Test win update
    result = update_player_stats("win", "rock", valid_id)
    assert result["rock"]["wins"] == 1
    assert result["totals"]["wins"] == 1

    # Test loss update
    result = update_player_stats("lose", "paper", valid_id)
    assert result["paper"]["losses"] == 1
    assert result["totals"]["losses"] == 1


# Fix 2: Update test_play_against_ai_valid
def test_play_against_ai_valid(client, mock_mongodb):
    """Test playing against AI with valid input."""
    # Create a valid ObjectId and corresponding document
    valid_id = str(ObjectId())
    initial_stats = {
        "rock": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "paper": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "scissors": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "totals": {"wins": 0, "losses": 0, "ties": 0},
    }

    mock_mongodb["test"]["stats"].insert_one(
        {"_id": ObjectId(valid_id), **initial_stats}
    )

    # Set the cookie with valid ObjectId
    client.set_cookie("db_object_id", valid_id)

    # Make the request
    response = client.post(
        "/play/ai", json={"player_name": "Test Player", "choice": "rock"}
    )

    # Assert the response
    assert response.status_code == 200
    data = response.get_json()
    assert data["player_name"] == "Test Player"
    assert data["player_choice"] == "rock"
    assert data["ai_choice"] in ["rock", "paper", "scissors"]
    assert data["result"] in ["win", "lose", "tie"]
    assert all(key in data["stats"] for key in ["wins", "losses", "ties"])


# Fix 3: Update test_result_endpoint_success
@patch("app.retry_request")
def test_result_endpoint_success(mock_retry, client, mock_mongodb):
    """Test the result endpoint with successful ML client response."""
    # Create a valid ObjectId and corresponding document
    valid_id = str(ObjectId())
    initial_stats = {
        "rock": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "paper": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "scissors": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "totals": {"wins": 0, "losses": 0, "ties": 0},
    }

    mock_mongodb["test"]["stats"].insert_one(
        {"_id": ObjectId(valid_id), **initial_stats}
    )

    # Set the cookie with valid ObjectId
    client.set_cookie("db_object_id", valid_id)

    # Mock the ML client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"gesture": "rock"}
    mock_response.status_code = 200
    mock_retry.return_value = mock_response

    # Prepare test data
    data = {"image": (BytesIO(b"test image data"), "test.jpg")}

    # Send the POST request
    response = client.post("/result", data=data, content_type="multipart/form-data")

    # Assert the response
    assert response.status_code == 200
    result = response.get_json()
    assert result["user_gesture"] == "rock"
    assert result["ai_choice"] in ["rock", "paper", "scissors"]
    assert result["result"] in ["It's a tie!", "You win!", "AI wins!"]


"""Additional test cases to improve coverage"""


def test_statistics_page_no_cookie(client, mock_mongodb):
    """Test statistics page when no cookie exists"""
    response = client.get("/statistics")
    assert response.status_code == 200
    assert "db_object_id" in response.headers.getlist("Set-Cookie")[0]


def test_generate_stats_doc(mock_mongodb):
    """Test generate_stats_doc function"""
    from app import generate_stats_doc

    doc_id = generate_stats_doc()
    assert doc_id is not None

    # Verify document structure
    doc = mock_mongodb["test"]["stats"].find_one({"_id": ObjectId(doc_id)})
    assert doc is not None
    assert all(key in doc for key in ["rock", "paper", "scissors", "totals"])
    assert all(key in doc["rock"] for key in ["wins", "losses", "ties", "total"])


def test_handle_start_game_complete(socket_client):
    """Test complete game start flow"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_name": "Player1",
        "player2_name": "Player2",
        "player1_sid": None,
        "player2_sid": None,
        "ready": {"player1": False, "player2": False},
    }

    # First player starts
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "123"})
    assert active_games[game_id]["ready"]["player1"] is True

    # Second player starts
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "456"})
    assert active_games[game_id]["ready"]["player2"] is True

    received = socket_client.get_received()
    assert any(msg["name"] == "proceed_to_game" for msg in received)


def test_handle_random_match_missing_player(socket_client):
    """Test random match with missing opponent"""
    socket_client.emit("random_match", {"player_name": "Player1", "player_id": "123"})

    received = socket_client.get_received()
    assert received[0]["name"] == "waiting"
    assert len(waiting_players) == 1

    # Verify waiting player data
    waiting_player = waiting_players[0]
    assert waiting_player["player_name"] == "Player1"
    assert waiting_player["player_id"] == "123"
    assert waiting_player["sid"] is not None


def test_retry_request_timeout_handling():
    """Test retry_request with timeout scenarios"""
    mock_files = {"image": MagicMock()}
    mock_files["image"].stream = BytesIO(b"test")

    with patch("requests.post") as mock_post:
        # Test immediate timeout
        mock_post.side_effect = RequestException("Timeout")
        result = retry_request(
            "http://test.com", mock_files, retries=1, delay=0, timeout=1
        )
        assert result is None
        assert mock_post.call_count == 1

        # Test eventual success after timeout
        mock_post.reset_mock()
        mock_post.side_effect = [
            RequestException("Timeout"),
            MagicMock(status_code=200),
        ]
        result = retry_request(
            "http://test.com", mock_files, retries=2, delay=0, timeout=1
        )
        assert result is not None
        assert mock_post.call_count == 2


def test_result_endpoint_ml_invalid_gesture(client, mock_mongodb):
    """Test result endpoint with invalid gesture from ML client"""
    valid_id = str(ObjectId())
    initial_stats = {
        "rock": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "paper": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "scissors": {"wins": 0, "losses": 0, "ties": 0, "total": 0},
        "totals": {"wins": 0, "losses": 0, "ties": 0},
    }

    mock_mongodb["test"]["stats"].insert_one(
        {"_id": ObjectId(valid_id), **initial_stats}
    )

    client.set_cookie("db_object_id", valid_id)

    with patch("app.retry_request") as mock_retry:
        mock_response = MagicMock()
        mock_response.json.return_value = {"gesture": "invalid"}
        mock_retry.return_value = mock_response

        data = {"image": (BytesIO(b"test image data"), "test.jpg")}
        response = client.post("/result", data=data, content_type="multipart/form-data")

        assert response.status_code == 500
        result = response.get_json()
        assert "error" in result


# Fix 1: Add missing countdown_timer import and fix test
from app import countdown_timer


def test_countdown_timer_ready_players(socket_client):
    """Test countdown timer when players become ready"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "ready": {"player1": False, "player2": False},
        "player1_choice": None,
        "player2_choice": None,
    }

    with patch("app.socketio.sleep") as mock_sleep, patch(
        "app.socketio.emit"
    ) as mock_emit:
        # Start countdown
        countdown_timer(game_id)

        # Verify countdown started
        assert mock_emit.called
        assert mock_sleep.called


def test_handle_submit_choice_invalid_data(socket_client):
    """Test submitting choice with invalid data"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_choice": None,
        "player2_choice": None,
        "player1_name": "Player1",
        "player2_name": "Player2",
    }

    # Test missing player_id
    socket_client.emit("submit_choice", {"game_id": game_id, "choice": "rock"})
    received = socket_client.get_received()
    assert any(msg["name"] == "error" for msg in received)

    socket_client.get_received()  # Clear messages

    # Test invalid player_id
    socket_client.emit(
        "submit_choice", {"game_id": game_id, "player_id": "999", "choice": "rock"}
    )
    received = socket_client.get_received()
    assert any(msg["name"] == "error" for msg in received)


def test_handle_cancel_waiting_invalid(socket_client):
    """Test canceling wait with invalid data"""
    # Test with missing player_id
    waiting_players.clear()  # Ensure clean state
    socket_client.emit("cancel_waiting", {})
    received = socket_client.get_received()
    assert len(received) == 1  # Should still get a response

    # Test with non-existent player
    waiting_players.clear()
    socket_client.emit("cancel_waiting", {"player_id": "nonexistent"})
    received = socket_client.get_received()
    assert len(received) == 1
    assert "waiting_cancelled" in received[0]["name"]


def test_handle_start_game_invalid_player(socket_client):
    """Test starting game with invalid player"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "ready": {"player1": False, "player2": False},
    }

    socket_client.emit("start_game", {"game_id": game_id, "player_id": "999"})
    received = socket_client.get_received()
    assert received[0]["name"] == "error"
    assert "Invalid player ID" in received[0]["args"][0]["message"]


def test_handle_start_game_both_ready(socket_client):
    """Test game start when both players ready"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_sid": "test_sid_1",
        "player2_sid": "test_sid_2",
        "ready": {"player1": False, "player2": False},
    }

    # First player ready
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "123"})
    socket_client.get_received()  # Clear messages

    # Second player ready
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "456"})
    received = socket_client.get_received()

    proceed_messages = [msg for msg in received if msg["name"] == "proceed_to_game"]
    assert len(proceed_messages) > 0


# Additional test to improve coverage


def test_handle_join_game_complete_flow(socket_client):
    """Test complete join game flow"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_sid": None,
        "player2_sid": None,
        "player1_name": "Player1",
        "player2_name": "Player2",
        "ready": {"player1": False, "player2": False},
    }

    # First player joins
    socket_client.emit("join_game", {"game_id": game_id, "player_id": "123"})
    received = socket_client.get_received()
    assert any(msg["name"] == "start_game" for msg in received)

    # Second player joins
    socket_client.emit("join_game", {"game_id": game_id, "player_id": "456"})
    received = socket_client.get_received()
    assert any(msg["name"] == "start_game" for msg in received)


def test_handle_random_match_complete_flow(socket_client):
    """Test complete random match flow"""
    # First player joins matchmaking
    socket_client.emit("random_match", {"player_name": "Player1", "player_id": "123"})
    received = socket_client.get_received()
    assert received[0]["name"] == "waiting"

    # Second player joins matchmaking
    socket_client.emit("random_match", {"player_name": "Player2", "player_id": "456"})
    received = socket_client.get_received()

    match_found = [msg for msg in received if msg["name"] == "match_found"]
    assert len(match_found) > 0
    game_data = match_found[0]["args"][0]
    assert "game_id" in game_data
    assert "opponent" in game_data


def test_countdown_timer_complete_flow(socket_client):
    """Test complete countdown timer flow"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "ready": {"player1": False, "player2": False},
    }

    with patch("app.socketio.sleep") as mock_sleep, patch(
        "app.socketio.emit"
    ) as mock_emit:
        countdown_timer(game_id)

        # Verify countdown emissions
        countdown_calls = [
            call[0] for call in mock_emit.call_args_list if call[0][0] == "countdown"
        ]
        assert len(countdown_calls) > 0

        # Verify match cancelled on timeout
        cancel_calls = [
            call[0]
            for call in mock_emit.call_args_list
            if call[0][0] == "match_cancelled"
        ]
        assert len(cancel_calls) > 0


def test_handle_start_game_both_ready(socket_client):
    """Test game start when both players ready"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_sid": "test_sid_1",
        "player2_sid": "test_sid_2",
        "ready": {"player1": False, "player2": False},
    }

    # First player ready
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "123"})
    socket_client.get_received()  # Clear messages

    # Second player ready
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "456"})
    received = socket_client.get_received()

    proceed_messages = [msg for msg in received if msg["name"] == "proceed_to_game"]
    assert len(proceed_messages) > 0


def test_handle_join_game_complete_flow(socket_client):
    """Test complete join game flow"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_sid": None,
        "player2_sid": None,
        "player1_name": "Player1",
        "player2_name": "Player2",
        "ready": {"player1": False, "player2": False},
    }

    # First player joins
    socket_client.emit("join_game", {"game_id": game_id, "player_id": "123"})
    received = socket_client.get_received()
    assert any(msg["name"] == "start_game" for msg in received)

    # Second player joins
    socket_client.emit("join_game", {"game_id": game_id, "player_id": "456"})
    received = socket_client.get_received()
    assert any(msg["name"] == "start_game" for msg in received)


def test_determine_winners_all_combinations():
    """Test all possible combinations for determine_winners function"""
    combinations = [
        ("rock", "rock", "It's a tie!"),
        ("rock", "paper", "AI wins!"),
        ("rock", "scissors", "You win!"),
        ("paper", "rock", "You win!"),
        ("paper", "paper", "It's a tie!"),
        ("paper", "scissors", "AI wins!"),
        ("scissors", "rock", "AI wins!"),
        ("scissors", "paper", "You win!"),
        ("scissors", "scissors", "It's a tie!"),
    ]

    for user_choice, ai_choice, expected in combinations:
        result = determine_winners(user_choice, ai_choice)
        assert result == expected


def test_handle_random_match_edge_cases(socket_client):
    """Test edge cases in random match handling"""
    # Test with empty game state
    active_games.clear()
    waiting_players.clear()

    # Test with multiple players in waiting
    socket_client.emit("random_match", {"player_name": "Player1", "player_id": "123"})
    socket_client.emit("random_match", {"player_name": "Player2", "player_id": "456"})
    socket_client.emit("random_match", {"player_name": "Player3", "player_id": "789"})

    received = socket_client.get_received()
    assert len([msg for msg in received if msg["name"] == "match_found"]) > 0
    assert len(waiting_players) == 1  # One player should remain waiting


def test_handle_submit_choice_missing_data(socket_client):
    """Test submitting choice with missing data"""
    socket_client.emit("submit_choice", {})
    received = socket_client.get_received()
    assert received[0]["name"] == "error"


def test_handle_join_game_missing_game(socket_client):
    """Test joining non-existent game"""
    socket_client.emit("join_game", {"game_id": str(uuid4()), "player_id": "123"})
    received = socket_client.get_received()
    assert received[0]["name"] == "error"
    assert "Invalid game ID" in received[0]["args"][0]["message"]


def test_handle_start_game_invalid_game(socket_client):
    """Test starting invalid game"""
    socket_client.emit("start_game", {"game_id": str(uuid4()), "player_id": "123"})
    received = socket_client.get_received()
    assert received[0]["name"] == "error"
    assert "Invalid game ID" in received[0]["args"][0]["message"]


def test_handle_submit_choice_with_both_choices(socket_client):
    """Test submitting choices for both players and getting result"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "player1_name": "Player1",
        "player2_name": "Player2",
        "player1_choice": None,
        "player2_choice": None,
        "player1_sid": "test_sid_1",
        "player2_sid": "test_sid_2",
        "ready": {"player1": True, "player2": True},
    }

    # Join the room
    socket_client.emit("join_game", {"game_id": game_id, "player_id": "123"})
    socket_client.get_received()

    # Both players submit choices
    socket_client.emit(
        "submit_choice", {"game_id": game_id, "player_id": "123", "choice": "rock"}
    )
    socket_client.emit(
        "submit_choice", {"game_id": game_id, "player_id": "456", "choice": "scissors"}
    )

    # Verify result
    received = socket_client.get_received()
    results = [msg for msg in received if msg["name"] == "game_result"]
    assert len(results) > 0
    assert "Player1 wins" in results[0]["args"][0]["result"]


def test_play_against_ai_missing_choice(client):
    """Test playing against AI with missing choice field"""
    valid_id = str(ObjectId())
    response = client.post("/play/ai", json={"player_name": "Test"})
    assert response.status_code == 400


def test_handle_start_game_double_ready(socket_client):
    """Test marking player ready twice"""
    game_id = "test_game"
    active_games[game_id] = {
        "player1_id": "123",
        "player2_id": "456",
        "ready": {"player1": False, "player2": False},
        "player1_sid": None,
        "player2_sid": None,
    }
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "123"})
    socket_client.emit("start_game", {"game_id": game_id, "player_id": "123"})

    assert active_games[game_id]["ready"]["player1"] is True
