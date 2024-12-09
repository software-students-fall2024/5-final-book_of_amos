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

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from flask_socketio import SocketIOTestClient
from requests.exceptions import RequestException

# this mocks the eventlet module
import sys

eventlet_mock = MagicMock()
eventlet_mock.monkey_patch = MagicMock()
sys.modules["eventlet"] = eventlet_mock
from app import (
    app,
    socketio,
    determine_winners,
    determine_ai_winner,
    retry_request,
    active_games,
    waiting_players,
    player_stats,
)


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
    """Mock MongoDB client using mongomock"""
    import mongomock

    mock_client = mongomock.MongoClient()
    monkeypatch.setattr("app.MongoClient", lambda uri: mock_client)
    return mock_client


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Reset game state before each test"""
    active_games.clear()
    waiting_players.clear()
    player_stats.update({"wins": 0, "losses": 0, "ties": 0})
    yield


# testing HTTP Routes
def test_home_page(client):
    """Test the home page route"""
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


def test_update_player_stats():
    """Test the update_player_stats function"""
    from app import update_player_stats

    initial_stats = player_stats.copy()

    update_player_stats("win")
    assert player_stats["wins"] == initial_stats["wins"] + 1

    update_player_stats("lose")
    assert player_stats["losses"] == initial_stats["losses"] + 1

    update_player_stats("tie")
    assert player_stats["ties"] == initial_stats["ties"] + 1


# Testing AI Play Route
def test_play_against_ai_valid(client, mock_mongodb):
    """Test playing against AI with valid input"""
    response = client.post("/play/ai", json={"player_name": "Test", "choice": "rock"})
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "player_name" in data
    assert data["player_name"] == "Test"
    assert "player_choice" in data
    assert data["player_choice"] == "rock"
    assert "ai_choice" in data
    assert data["ai_choice"] in ["rock", "paper", "scissors"]
    assert "result" in data
    assert data["result"] in ["win", "lose", "tie"]
    assert "stats" in data
    assert all(key in data["stats"] for key in ["wins", "losses", "ties"])


def test_play_against_ai_invalid(client):
    """Test playing against AI with invalid input"""
    response = client.post(
        "/play/ai", json={"player_name": "Test", "choice": "invalid"}
    )
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Invalid choice"


# Test Result Route
@patch("app.retry_request")
def test_result_endpoint_success(mock_retry, client, mock_mongodb):
    """Test the result endpoint with successful ML client response"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"gesture": "rock"}
    mock_response.status_code = 200
    mock_retry.return_value = mock_response

    data = {"image": (BytesIO(b"test image data"), "test.jpg")}
    response = client.post("/result", data=data, content_type="multipart/form-data")

    assert response.status_code == 200
    result = json.loads(response.data)
    assert "user_gesture" in result
    assert result["user_gesture"] == "rock"
    assert "ai_choice" in result
    assert result["ai_choice"] in ["rock", "paper", "scissors"]
    assert "result" in result
    assert result["result"] in ["It's a tie!", "You win!", "AI wins!"]


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
    """Test the result endpoint when ML client fails"""
    mock_retry.return_value = None

    data = {"image": (BytesIO(b"test image data"), "test.jpg")}
    response = client.post("/result", data=data, content_type="multipart/form-data")

    assert response.status_code == 500
    result = json.loads(response.data)
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
