import pytest
from state.table_builder import (
    TableBuildError,
    build_table,
    find_rows,
    humanize,
    normalize_columns,
)

CATEGORIES = {
    "modelTitle": "Demo",
    "categories": [
        {"name": "Walls", "elementCount": 12, "categoryType": "Model"},
        {"name": "Pipes", "elementCount": 40, "categoryType": "Model"},
        {"name": "Doors", "elementCount": 3, "categoryType": "Model"},
    ],
}


def test_humanize():
    assert humanize("elementCount") == "Element count"
    assert humanize("built_in_category") == "Built in category"


def test_auto_detects_the_list_of_objects():
    key, rows = find_rows(CATEGORIES)
    assert key == "categories"
    assert len(rows) == 3


def test_build_table_columns_sort_and_headers():
    table = build_table(
        CATEGORIES, columns=["name", "elementCount"], sort_by="elementCount", descending=True
    )
    assert table["columns"] == ["Name", "Element count"]
    assert table["rows"] == [["Pipes", 40], ["Walls", 12], ["Doors", 3]]
    assert table["totalRows"] == 3
    assert table["truncated"] is False


def test_limit_truncates_and_reports_it():
    table = build_table(CATEGORIES, limit=2)
    assert len(table["rows"]) == 2
    assert table["totalRows"] == 3
    assert table["truncated"] is True


def test_flat_result_becomes_property_value_rows():
    table = build_table({"title": "Demo", "isWorkshared": False, "extra": {"a": 1}})
    assert table["columns"] == ["Property", "Value"]
    # the Value column mixes text and bool, so it is converted to text (Yes/No)
    assert table["rows"] == [
        ["Title", "Demo"],
        ["Is workshared", "No"],
        ["Extra", '{"a":1}'],
    ]


def test_mixed_and_missing_values_sort_without_errors():
    result = {"rows": [{"v": 2}, {"v": "b"}, {}, {"v": 1}]}
    values = [r[0] for r in build_table(result, sort_by="v")["rows"]]
    assert values == ["1", "2", "b", None]  # mixed column -> text, missing stays None


@pytest.mark.parametrize(
    "kwargs",
    [{"columns": ["nope"]}, {"sort_by": "nope"}, {"list_key": "modelTitle"}, {"list_key": "x.y"}],
)
def test_bad_requests_raise_table_build_error(kwargs):
    with pytest.raises(TableBuildError):
        build_table(CATEGORIES, **kwargs)


def test_normalize_keeps_pure_columns_and_none():
    rows = [["a", 1, True], ["b", 2.5, None], ["c", None, False]]
    assert normalize_columns(rows) == rows


def test_normalize_converts_only_the_mixed_column():
    rows = [["a", 1], ["b", "x"], ["c", None]]
    assert normalize_columns(rows) == [["a", "1"], ["b", "x"], ["c", None]]
