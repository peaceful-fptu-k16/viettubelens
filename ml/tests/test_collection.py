from viettubelens_ml.collect import is_probably_vietnamese, pseudonymous_id
from viettubelens_ml.pseudo_label import relevance_probability


def test_vietnamese_detection_supports_diacritics_and_plain_text() -> None:
    assert is_probably_vietnamese("Video này rất hay và dễ hiểu")
    assert is_probably_vietnamese("minh xem video nay voi ban")
    assert not is_probably_vietnamese("This tutorial is very helpful")


def test_comment_identifier_is_pseudonymous_and_deterministic() -> None:
    source = "Ugxl-source-comment-id"
    assert pseudonymous_id(source) == pseudonymous_id(source)
    assert source not in pseudonymous_id(source)
    assert len(pseudonymous_id(source)) == 24


def test_relevance_rules_downrank_spam() -> None:
    relevant = relevance_probability(
        "Phần so sánh camera trong video rất hữu ích", "Đánh giá camera điện thoại"
    )
    spam = relevance_probability("Ai còn xem 2026, sub chéo nhé", "Đánh giá camera")
    assert relevant >= 0.5
    assert spam < 0.5
