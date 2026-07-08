from riivault.nlp.sentiment import sentiment_compound


def test_positive_text_is_positive():
    assert sentiment_compound("I absolutely love this, it's wonderful and amazing!") > 0.3


def test_negative_text_is_negative():
    assert sentiment_compound("This is terrible, awful — I hate it and it's broken.") < -0.3


def test_empty_or_blank_is_zero():
    assert sentiment_compound("") == 0.0
    assert sentiment_compound("   ") == 0.0
    assert sentiment_compound(None) == 0.0


def test_result_stays_in_bounds():
    for text in ["great great great awesome fantastic love", "the table has four legs"]:
        value = sentiment_compound(text)
        assert -1.0 <= value <= 1.0
