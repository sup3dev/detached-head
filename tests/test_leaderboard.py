"""Tests for the speedrun leaderboard validator and board updater."""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from detached_head.leaderboard import (  # noqa: E402
    BOARD_BEGIN,
    BOARD_END,
    load_graph,
    main,
    update_leaderboard,
    validate_run,
)

# Miniature synthetic graph (the real data/graph.json does not exist yet):
# n0 --F--> n1 (arena, hp=1), n1 --X--> WIN. L/R turn in place on n0.
BASE_GRAPH = {
    "meta": {"name": "TEST", "level": "test-01", "moves": ["F", "B", "L", "R", "X"]},
    "start": "n0",
    "win": "WIN",
    "nodes": {
        "n0": {
            "cell": [0, 0], "angle": "N", "zone": "main", "kind": "normal",
            "key": 0, "hp": None,
            "moves": {"F": "n1", "B": None, "L": "n0w", "R": None, "X": "n0"},
        },
        "n0w": {
            "cell": [0, 0], "angle": "W", "zone": "main", "kind": "normal",
            "key": 0, "hp": None,
            "moves": {"F": None, "B": None, "L": None, "R": "n0", "X": "n0w"},
        },
        "n1": {
            "cell": [0, 1], "angle": "N", "zone": "arena", "kind": "arena",
            "key": None, "hp": 1,
            "moves": {"F": None, "B": "n0", "L": None, "R": None, "X": "WIN"},
        },
        "WIN": {"kind": "win", "moves": {}},
    },
}


@pytest.fixture()
def graph():
    return copy.deepcopy(BASE_GRAPH)


@pytest.fixture()
def graph_file(tmp_path):
    path = tmp_path / "graph.json"
    path.write_bytes(json.dumps(BASE_GRAPH).encode("utf-8"))
    return path


def make_board(tmp_path, text=None):
    board = tmp_path / "LEADERBOARD.md"
    if text is not None:
        board.write_bytes(text.encode("utf-8"))
    return board


def entry(player, clicks, day, route="FX"):
    return {"player": player, "route": route, "clicks": clicks, "date": day}


# --- load_graph -----------------------------------------------------------


def test_load_graph_returns_dict(graph_file):
    graph = load_graph(graph_file)
    assert graph["start"] == "n0"
    assert graph["win"] == "WIN"
    assert "WIN" in graph["nodes"]


def test_load_graph_rejects_incomplete_graph(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(json.dumps({"start": "n0"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_graph(path)


# --- validate_run ---------------------------------------------------------


def test_happy_path_reaches_win(graph):
    result = validate_run(graph, "FX")
    assert result == {"ok": True, "clicks": 2, "end": "WIN"}


@pytest.mark.parametrize("route", ["fx", "f x", "F,X", " , F,,,x , "])
def test_route_case_and_separators_ignored(graph, route):
    assert validate_run(graph, route) == {"ok": True, "clicks": 2, "end": "WIN"}


def test_turn_and_back_moves_are_clicks(graph):
    # L (turn) + R (turn back) + F + B (step back) + F + X = 6 clicks.
    result = validate_run(graph, "LRFBFX")
    assert result == {"ok": True, "clicks": 6, "end": "WIN"}


def test_invalid_token_rejected(graph):
    result = validate_run(graph, "FQX")
    assert result["ok"] is False
    assert result["clicks"] == 1
    assert "token 1" in result["error"]
    assert "'Q'" in result["error"]
    assert "not a valid move" in result["error"]


def test_move_into_wall_rejected(graph):
    result = validate_run(graph, "FF")
    assert result["ok"] is False
    assert result["clicks"] == 1
    assert "token 1" in result["error"]
    assert "wall" in result["error"]


def test_move_to_unknown_node_rejected(graph):
    graph["nodes"]["n0"]["moves"]["F"] = "ghost"
    result = validate_run(graph, "F")
    assert result["ok"] is False
    assert result["clicks"] == 0
    assert "unknown node 'ghost'" in result["error"]


@pytest.mark.parametrize("route", ["X", "F", "FB"])
def test_route_not_reaching_win_rejected(graph, route):
    result = validate_run(graph, route)
    assert result["ok"] is False
    assert result["error"] == "run did not reach WIN"
    assert result["clicks"] == len(route)


@pytest.mark.parametrize("route", ["", "   ", " , , "])
def test_empty_route_rejected(graph, route):
    result = validate_run(graph, route)
    assert result == {"ok": False, "error": "route is empty", "clicks": 0}


def test_tokens_after_win_rejected(graph):
    # WIN has no outgoing links, so anything after the winning shot fails.
    result = validate_run(graph, "FXX")
    assert result["ok"] is False
    assert result["clicks"] == 2
    assert "token 2" in result["error"]


# --- CLI ------------------------------------------------------------------


def test_cli_validate_ok(graph_file, capsys):
    code = main(["FX", "--graph", str(graph_file)])
    out = capsys.readouterr().out
    assert code == 0
    assert "OK" in out
    assert "2 clicks" in out


def test_cli_validate_failure(graph_file, capsys):
    code = main(["FF", "--graph", str(graph_file)])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL" in out


def test_cli_module_invocation(graph_file):
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    proc = subprocess.run(
        [sys.executable, "-m", "detached_head.leaderboard", "FX", "--graph", str(graph_file)],
        capture_output=True, text=True, env=env, cwd=str(SRC.parent),
    )
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_cli_submit_updates_board(graph_file, tmp_path, capsys):
    board = tmp_path / "LEADERBOARD.md"
    code = main(["--submit", "alice", "FX", "--graph", str(graph_file), "--board", str(board)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Run accepted: 2 clicks" in out
    assert "#1" in out
    text = board.read_bytes().decode("utf-8")
    assert BOARD_BEGIN in text and BOARD_END in text
    assert "| 1 | alice | 2 |" in text


# --- update_leaderboard ---------------------------------------------------


def test_update_inserts_markers_into_missing_file(tmp_path):
    board = make_board(tmp_path)
    update_leaderboard(board, entry("alice", 5, "2026-01-01"))
    text = board.read_bytes().decode("utf-8")
    assert text == (
        f"{BOARD_BEGIN}\n"
        "| # | Player | Clicks | Date |\n"
        "|---|---|---|---|\n"
        "| 1 | alice | 5 | 2026-01-01 |\n"
        f"{BOARD_END}\n"
    )


def test_update_preserves_text_outside_markers(tmp_path):
    original = (
        "# Speedrun board\n\n"
        "Intro paragraph.\n\n"
        f"{BOARD_BEGIN}\n"
        "| # | Player | Clicks | Date |\n"
        "|---|---|---|---|\n"
        "| 1 | bob | 9 | 2026-01-01 |\n"
        f"{BOARD_END}\n"
        "\nFooter.\n"
    )
    board = make_board(tmp_path, original)
    update_leaderboard(board, entry("alice", 7, "2026-02-02"))
    text = board.read_bytes().decode("utf-8")

    head, rest = text.split(BOARD_BEGIN, 1)
    _, tail = rest.split(BOARD_END, 1)
    assert head == "# Speedrun board\n\nIntro paragraph.\n\n"
    assert tail == "\n\nFooter.\n"
    assert "| 1 | alice | 7 | 2026-02-02 |" in text
    assert "| 2 | bob | 9 | 2026-01-01 |" in text


def test_update_sorts_by_clicks_then_date(tmp_path):
    board = make_board(tmp_path)
    update_leaderboard(board, entry("bob", 7, "2026-03-03"))
    update_leaderboard(board, entry("carol", 7, "2026-01-01"))
    update_leaderboard(board, entry("dave", 3, "2026-05-05"))
    text = board.read_bytes().decode("utf-8")
    assert text.index("| 1 | dave | 3 |") < text.index("| 2 | carol | 7 |")
    assert text.index("| 2 | carol | 7 |") < text.index("| 3 | bob | 7 |")


def test_duplicate_player_keeps_best_result(tmp_path):
    board = make_board(tmp_path)
    update_leaderboard(board, entry("alice", 8, "2026-01-01"))
    update_leaderboard(board, entry("alice", 5, "2026-02-02"))
    assert board.read_bytes().decode("utf-8").count("| alice |") == 1
    assert "| 1 | alice | 5 | 2026-02-02 |" in board.read_bytes().decode("utf-8")


def test_duplicate_player_worse_result_discarded(tmp_path):
    board = make_board(tmp_path)
    update_leaderboard(board, entry("alice", 5, "2026-01-01"))
    update_leaderboard(board, entry("alice", 8, "2026-02-02"))
    text = board.read_bytes().decode("utf-8")
    assert text.count("| alice |") == 1
    assert "| 1 | alice | 5 | 2026-01-01 |" in text


def test_duplicate_player_equal_clicks_keeps_first_date(tmp_path):
    board = make_board(tmp_path)
    update_leaderboard(board, entry("alice", 5, "2026-01-01"))
    update_leaderboard(board, entry("alice", 5, "2026-02-02"))
    assert "| 1 | alice | 5 | 2026-01-01 |" in board.read_bytes().decode("utf-8")
