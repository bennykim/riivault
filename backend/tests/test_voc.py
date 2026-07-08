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
