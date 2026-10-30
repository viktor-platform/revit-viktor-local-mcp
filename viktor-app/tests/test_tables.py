import json

import pytest
from state.tables import (
    clear_table,
    read_table,
    save_table,
    storage_prefix,
)


class FakeFile:
    def __init__(self, data):
        self.data = data

    def getvalue_binary(self):
        return self.data.encode() if isinstance(self.data, str) else self.data

    def getvalue(self):
        return self.data


class FakeStorage:
    """Minimal stand-in for vkt.Storage()."""

    def __init__(self):
        self.items = {}

    def set(self, key, *, data, scope):
        assert scope == "entity"
        self.items[key] = data.getvalue()

    def get(self, key, *, scope):
        assert scope == "entity"
        if key not in self.items:
            raise FileNotFoundError(key)
        return FakeFile(self.items[key])

    def list(self, *, prefix=None, scope):
        return {k: FakeFile(v) for k, v in self.items.items() if k.startswith(prefix or "")}

    def delete(self, key, *, scope):
        if key not in self.items:
            raise FileNotFoundError(key)
        del self.items[key]


def test_storage_prefix_separates_entities_and_workspaces():
    assert storage_prefix(7, 3) == "revit-mcp-template:entity:7"
    assert storage_prefix(None, 3) == "revit-mcp-template:workspace:3"
    assert storage_prefix(None, None) == "revit-mcp-template:local"


def test_save_then_read_round_trips_a_table():
    storage = FakeStorage()
    save_table("p", title="T", columns=["a", "b"], rows=[[1, "x"], [2, "y"]], storage=storage)

    table = read_table("p", storage=storage)

    assert table["title"] == "T"
    assert table["columns"] == ["a", "b"]
    assert table["rows"] == [[1, "x"], [2, "y"]]
    assert json.loads(next(iter(storage.items.values())))["updatedAt"]


def test_read_table_is_none_when_nothing_saved():
    assert read_table("p", storage=FakeStorage()) is None


def test_save_table_validates_shape():
    with pytest.raises(ValueError, match="column"):
        save_table("p", title="T", columns=[], rows=[], storage=FakeStorage())
    with pytest.raises(ValueError, match="one value per column"):
        save_table("p", title="T", columns=["a"], rows=[[1, 2]], storage=FakeStorage())


def test_clear_table_is_idempotent():
    storage = FakeStorage()
    save_table("p", title="T", columns=["a"], rows=[[1]], storage=storage)
    clear_table("p", storage=storage)
    clear_table("p", storage=storage)  # second call must not raise
    assert read_table("p", storage=storage) is None
