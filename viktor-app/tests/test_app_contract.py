import unittest
from unittest.mock import patch

import viktor as vkt
from app import Controller, Parametrization, is_first_user_turn
from viktor.testing import mock_View


class FakeConversation:
    def __init__(self, roles):
        self._messages = [{"role": r, "content": "x"} for r in roles]

    def get_messages(self):
        return self._messages


class TestAppContract(unittest.TestCase):
    def test_parametrization_has_a_chat_wired_to_call_agent(self):
        self.assertIsInstance(Parametrization.chat, vkt.Chat)
        # vkt.Chat(method="call_agent") needs a Controller method with that name.
        self.assertTrue(callable(getattr(Controller, "call_agent", None)))

    def test_first_user_turn_detection(self):
        self.assertTrue(is_first_user_turn(FakeConversation(["user"])))
        self.assertFalse(
            is_first_user_turn(FakeConversation(["user", "assistant", "user"]))
        )
        self.assertFalse(is_first_user_turn(None))

    # VIKTOR's mock_View lets us call a decorated view as plain Python. It only works
    # on unittest.TestCase methods (pytest still collects and runs them).
    @mock_View(Controller)
    def test_table_view_shows_placeholder_before_any_result(self):
        with patch("app.read_table", return_value=None):
            result = Controller().results_table(params=None, entity_id=1)
        self.assertIsInstance(result, vkt.TableResult)
        self.assertIn("No results yet", result.data[0][0])

    @mock_View(Controller)
    def test_table_view_renders_the_stored_table(self):
        stored = {
            "title": "Categories",
            "columns": ["Category", "Elements"],
            "rows": [["Walls", 12], ["Pipes", 4]],
        }
        with patch("app.read_table", return_value=stored):
            result = Controller().results_table(params=None, entity_id=1)
        self.assertEqual(result.data, stored["rows"])
        self.assertEqual(result.column_headers, stored["columns"])

    @mock_View(Controller)
    def test_stored_mixed_type_table_serialises_with_the_real_sdk(self):
        # Regression: a Property/Value table (text + bool) crashed the view in VIKTOR.
        stored = {
            "title": "Model",
            "columns": ["Property", "Value"],
            "rows": [["Title", "Demo"], ["Workshared", False], ["Version", 2027]],
        }
        with patch("app.read_table", return_value=stored):
            result = Controller().results_table(params=None, entity_id=1)
        result._serialize()  # raises ValueError for mixed-type columns
