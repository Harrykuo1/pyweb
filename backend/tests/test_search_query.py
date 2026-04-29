"""Pure-function tests for app.core.search_query.parse.

Parser semantics — Google-style:
  * Implicit AND between adjacent terms.
  * Uppercase ``OR`` splits at the top level (AND > OR in precedence).
  * ``-prefix`` and uppercase ``NOT`` negate; ``-`` only counts when attached
    to the next token (no intervening whitespace).
  * Double-quoted phrases preserve internal whitespace.

This case table is mirrored by the frontend parser in
``frontend/src/utils/searchQuery.spec.js`` — keep them in lockstep.
"""

from app.core.search_query import Term, parse


def t(text: str, negate: bool = False) -> Term:
    return Term(text=text, negate=negate)


# ---------- empty / whitespace ----------


def test_parse_empty_returns_no_groups():
    assert parse("") == []


def test_parse_whitespace_only_returns_no_groups():
    assert parse("   \t  ") == []


# ---------- single term / implicit AND ----------


def test_parse_single_word():
    assert parse("react") == [[t("react")]]


def test_parse_implicit_and_two_words():
    assert parse("react vue") == [[t("react"), t("vue")]]


def test_parse_collapses_multiple_spaces():
    assert parse("react   vue") == [[t("react"), t("vue")]]


# ---------- OR (Google-style: low precedence) ----------


def test_parse_or_splits_into_two_groups():
    assert parse("react OR vue") == [[t("react")], [t("vue")]]


def test_parse_or_low_precedence_against_and():
    # `senior react OR vue junior` -> (senior AND react) OR (vue AND junior)
    assert parse("senior react OR vue junior") == [
        [t("senior"), t("react")],
        [t("vue"), t("junior")],
    ]


def test_parse_lowercase_or_is_a_normal_term():
    assert parse("react or vue") == [[t("react"), t("or"), t("vue")]]


def test_parse_leading_or_is_ignored():
    assert parse("OR react") == [[t("react")]]


def test_parse_trailing_or_is_ignored():
    assert parse("react OR") == [[t("react")]]


def test_parse_consecutive_or_collapses_empty_groups():
    assert parse("react OR OR vue") == [[t("react")], [t("vue")]]


# ---------- negation ----------


def test_parse_dash_prefix_negates():
    assert parse("react -junior") == [[t("react"), t("junior", negate=True)]]


def test_parse_uppercase_not_negates_following_token():
    assert parse("react NOT junior") == [[t("react"), t("junior", negate=True)]]


def test_parse_lowercase_not_is_a_normal_term():
    assert parse("react not junior") == [[t("react"), t("not"), t("junior")]]


def test_parse_dash_with_no_next_token_is_ignored():
    assert parse("react -") == [[t("react")]]


def test_parse_dash_with_space_is_ignored():
    # `- foo` is not a negation — dash detached from term, dropped as noise.
    assert parse("react - foo") == [[t("react"), t("foo")]]


def test_parse_double_dash_keeps_inner_dash_in_text():
    # `--foo` -> negate the literal substring `-foo`.
    assert parse("--foo") == [[t("-foo", negate=True)]]


def test_parse_not_alone_is_noop():
    assert parse("NOT") == []


def test_parse_trailing_not_is_noop():
    assert parse("react NOT") == [[t("react")]]


def test_parse_not_before_or_is_reset():
    # Pending NOT is cleared by OR; the second group starts fresh.
    assert parse("NOT OR foo") == [[t("foo")]]


def test_parse_dash_or_is_literal_term_not_operator():
    # `-OR` -> negate the literal string "OR", not a group separator.
    assert parse("react -OR vue") == [
        [t("react"), t("OR", negate=True), t("vue")],
    ]


# ---------- phrases ----------


def test_parse_quoted_phrase_preserves_whitespace():
    assert parse('"team lead"') == [[t("team lead")]]


def test_parse_phrase_alongside_other_terms():
    assert parse('senior "team lead"') == [[t("senior"), t("team lead")]]


def test_parse_negated_phrase_dash_prefix():
    assert parse('-"team lead"') == [[t("team lead", negate=True)]]


def test_parse_negated_phrase_not_keyword():
    assert parse('NOT "team lead"') == [[t("team lead", negate=True)]]


def test_parse_empty_quotes_ignored():
    assert parse('react "" vue') == [[t("react"), t("vue")]]


def test_parse_quoted_or_is_literal():
    assert parse('"react OR vue"') == [[t("react OR vue")]]


def test_parse_quoted_dash_is_literal():
    assert parse('"-junior"') == [[t("-junior")]]


def test_parse_unterminated_quote_treats_rest_as_phrase():
    assert parse('react "team lead') == [[t("react"), t("team lead")]]


# ---------- combined ----------


def test_parse_combined_realistic_query():
    # `senior react OR vue -junior "team lead"` (Google-style)
    # = (senior AND react) OR (vue AND NOT junior AND "team lead")
    assert parse('senior react OR vue -junior "team lead"') == [
        [t("senior"), t("react")],
        [t("vue"), t("junior", negate=True), t("team lead")],
    ]


def test_parse_combined_with_not_keyword_both_groups():
    assert parse("react NOT junior OR vue NOT senior") == [
        [t("react"), t("junior", negate=True)],
        [t("vue"), t("senior", negate=True)],
    ]
