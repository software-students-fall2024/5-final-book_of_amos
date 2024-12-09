import pytest
import json
from flask import url_for
from app import app, socketio, player_stats


@pytest.fixture
def client():
    """Set up the test client for Flask."""
    with app.test_client() as client:
        yield client


@pytest.fixture
def reset_player_stats():
    """Reset player stats before each test."""
    global player_stats
    player_stats = {"wins": 0, "losses": 0, "ties": 0}
    yield


# Route Tests


def test_home_route_content(client):
    """Test the content of the home route."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Rock-Paper-Scissors" in response.data
    assert b"Welcome" in response.data


def test_ai_route_redirect(client):
    """Test AI route with a possible redirect."""
    response = client.get("/ai", follow_redirects=True)
    assert response.status_code == 200
    assert b"AI" in response.data


def test_real_person_route_content(client):
    """Test content on the real person page."""
    response = client.get("/real_person")
    assert b"Multiplayer" in response.data
    assert response.status_code == 200


def test_nonexistent_route(client):
    """Test a route that does not exist."""
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert b"Not Found" in response.data


# Result Route Tests


def test_result_route_with_valid_file(client, mocker):
    """Test the result route with a valid file."""
    mock_ml_response = {"gesture": "rock"}
    mock_post = mocker.patch("requests.post", return_value=mocker.Mock(
        json=lambda: mock_ml_response, status_code=200))
    file_data = (b"fakeimagecontent", "image.jpg")
    response = client.post("/result", data={"image": file_data})
    assert response.status_code == 200
    assert mock_post.called
    assert b"user_gesture" in response.data


def test_result_route_invalid_ml_response(client, mocker):
    """Test result route with an invalid ML response."""
    mock_post = mocker.patch("requests.post", return_value=mocker.Mock(
        json=lambda: {}, status_code=200))
    file_data = (b"fakeimagecontent", "image.jpg")
    response = client.post("/result", data={"image": file_data})
    assert response.status_code == 500
    assert b"Invalid response from ML client" in response.data


def test_result_route_timeout(client, mocker):
    """Test the result route when the ML client times out."""
    mocker.patch("requests.post", side_effect=Exception("Timeout"))
    file_data = (b"fakeimagecontent", "image.jpg")
    response = client.post("/result", data={"image": file_data})
    assert response.status_code == 500
    assert b"ML client did not respond" in response.data


def test_result_route_file_not_image(client):
    """Test the result route with a non-image file."""
    response = client.post(
        "/result", data={"image": (b"textcontent", "file.txt")})
    assert response.status_code == 400
    assert b"Invalid file provided" in response.data


# Play Against AI Tests


def test_play_ai_route_tie(client):
    """Test playing against the AI with a tie result."""
    response = client.post(
        "/play/ai",
        data=json.dumps({"player_name": "TestPlayer", "choice": "rock"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    response_data = response.get_json()
    if response_data["ai_choice"] == "rock":
        assert response_data["result"] == "tie"


def test_play_ai_route_win(client):
    """Test playing against the AI with a win."""
    response = client.post(
        "/play/ai",
        data=json.dumps({"player_name": "TestPlayer", "choice": "rock"}),
        content_type="application/json",
    )
    response_data = response.get_json()
    if response_data["ai_choice"] == "scissors":
        assert response_data["result"] == "win"


def test_play_ai_route_lose(client):
    """Test playing against the AI with a loss."""
    response = client.post(
        "/play/ai",
        data=json.dumps({"player_name": "TestPlayer", "choice": "rock"}),
        content_type="application/json",
    )
    response_data = response.get_json()
    if response_data["ai_choice"] == "paper":
        assert response_data["result"] == "lose"


def test_play_ai_route_invalid_json(client):
    """Test playing against AI with invalid JSON input."""
    response = client.post("/play/ai", data="not a json",
                           content_type="application/json")
    assert response.status_code == 400
    assert b"Invalid choice" in response.data


# Stats and Helper Function Tests


def test_update_player_stats_win(reset_player_stats):
    """Test updating stats after a win."""
    from app import update_player_stats

    update_player_stats("win")
    assert player_stats["wins"] == 1
    assert player_stats["losses"] == 0
    assert player_stats["ties"] == 0


def test_update_player_stats_loss(reset_player_stats):
    """Test updating stats after a loss."""
    from app import update_player_stats

    update_player_stats("lose")
    assert player_stats["losses"] == 1
    assert player_stats["wins"] == 0
    assert player_stats["ties"] == 0


def test_update_player_stats_tie(reset_player_stats):
    """Test updating stats after a tie."""
    from app import update_player_stats

    update_player_stats("tie")
    assert player_stats["ties"] == 1
    assert player_stats["wins"] == 0
    assert player_stats["losses"] == 0


def test_reset_game():
    """Test resetting a game."""
    from app import reset_game, active_games

    game_id = "test_game"
    active_games[game_id] = {
        "player1_choice": "rock", "player2_choice": "paper"}
    reset_game(game_id)
    assert active_games[game_id]["player1_choice"] is None
    assert active_games[game_id]["player2_choice"] is None


# Socket.IO Tests


@pytest.fixture
def socketio_client():
    """Set up the Socket.IO test client."""
    with socketio.test_client(app) as client:
        yield client


def test_submit_choice_valid_game(socketio_client, mocker):
    """Test submitting a valid choice in a valid game."""
    mocker.patch("app.active_games", {"test_game": {"player1_id": "player1"}})
    socketio_client.emit("submit_choice", {
                         "game_id": "test_game", "player_id": "player1", "choice": "rock"})
    received = socketio_client.get_received()
    assert any("game_result" in event["name"] for event in received)


def test_submit_choice_invalid_game(socketio_client):
    """Test submitting a choice to an invalid game."""
    socketio_client.emit("submit_choice", {
                         "game_id": "invalid", "player_id": "player1", "choice": "rock"})
    received = socketio_client.get_received()
    assert any("error" in event["name"] for event in received)


def test_handle_disconnect(socketio_client, mocker):
    """Test handling a player disconnect."""
    mock_active_games = {"test_game": {"player1_sid": socketio_client.sid}}
    mocker.patch("app.active_games", mock_active_games)
    socketio_client.disconnect()
    assert mock_active_games["test_game"]["player1_sid"] is None
