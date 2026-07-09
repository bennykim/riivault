from riivault.nlp.voc import VOC_KINDS, parse_voc_response


def test_kinds_are_expected():
    assert VOC_KINDS == {
        "pain_point", "feature_request", "switch_intent", "bug", "praise"
    }


def test_parse_plain_json_array():
    raw = (
        '[{"index":0,"kind":"pain_point",'
        '"normalized_text":"Pricing is too high","entity_name":"Zapier"}]'
    )
    out = parse_voc_response(raw)
    assert out == [
        {
            "kind": "pain_point",
            "normalized_text": "Pricing is too high",
            "entity_name": "Zapier",
            "index": 0,
        }
    ]


def test_parse_with_prose_and_code_fence():
    raw = (
        "Here is the result:\n```json\n"
        '[{"kind":"praise","normalized_text":"Users love the UX"}]\n```'
    )
    out = parse_voc_response(raw)
    assert out == [
        {"kind": "praise", "normalized_text": "Users love the UX", "entity_name": None}
    ]


def test_invalid_items_are_skipped():
    raw = (
        '[{"kind":"nope","normalized_text":"x"},'
        '{"kind":"bug","normalized_text":""},'
        '{"kind":"bug","normalized_text":"App crashes on save"}]'
    )
    out = parse_voc_response(raw)
    assert len(out) == 1
    assert out[0]["kind"] == "bug"
    assert out[0]["normalized_text"] == "App crashes on save"


def test_wrapped_results_object():
    raw = '{"results":[{"kind":"feature_request","normalized_text":"Add dark mode"}]}'
    out = parse_voc_response(raw)
    assert len(out) == 1
    assert out[0]["kind"] == "feature_request"
    assert out[0]["entity_name"] is None


def test_garbage_returns_empty():
    assert parse_voc_response("not json at all") == []
    assert parse_voc_response("") == []


def test_truncated_array_salvages_complete_elements():
    # Simulates an output-limit truncation mid-element: the first two records
    # are complete, the third is cut off and must be dropped.
    raw = (
        '[{"index": 0, "kind": "bug", "normalized_text": "Database name error on start"},'
        ' {"index": 1, "kind": "pain_point", "normalized_text": "Menu invisible in Brave"},'
        ' {"index": 2, "kind": "feature_re'
    )
    records = parse_voc_response(raw)
    assert [r["index"] for r in records] == [0, 1]
    assert records[0]["kind"] == "bug"


def test_truncated_with_no_complete_element_returns_empty():
    assert parse_voc_response('[{"index": 0, "kind": "bu') == []
