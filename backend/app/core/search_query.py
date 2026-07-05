"""Boolean search query parser (Google-style precedence).

Supported syntax:
  * Implicit AND between adjacent terms: ``react vue`` requires both.
  * ``OR`` (uppercase) splits the query at the top level — AND binds tighter:
    ``a b OR c d`` parses as ``(a AND b) OR (c AND d)``.
  * Negation via ``-prefix`` or ``NOT`` keyword: ``-junior`` / ``NOT junior``.
  * Quoted phrases preserve internal whitespace: ``"team lead"``.
  * Negated phrases: ``-"team lead"`` and ``NOT "team lead"``.

``parse()`` is a pure function (stdlib only) and is mirrored verbatim by
the JS frontend in ``frontend/src/utils/searchQuery.js``. ``build_ilike_filter()``
turns the IR into a SQLAlchemy expression for use by routers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import and_, not_, or_
from sqlalchemy.sql import ColumnElement


@dataclass(frozen=True)
class Term:
    text: str
    negate: bool = False


# An AndGroup is a list[Term] (all must match, with negation respected).
# parse() returns list[AndGroup] — outer list combined with OR.
# Empty outer list = "no filter".


def _tokenize(q: str) -> list[tuple[str, bool, bool]]:
    """Split q into ``(text, is_phrase, has_negate_prefix)`` tokens.

    A leading ``-`` only attaches to the next token if there is no whitespace
    between them — ``- foo`` keeps the dash detached and drops it as noise.
    Empty quotes (``""``) and lone dashes are dropped.
    """
    tokens: list[tuple[str, bool, bool]] = []
    n = len(q)
    i = 0
    while i < n:
        c = q[i]
        if c.isspace():
            i += 1
            continue
        negate = False
        if c == "-":
            if i + 1 < n and not q[i + 1].isspace():
                negate = True
                i += 1
                c = q[i]
            else:
                i += 1
                continue
        if c == '"':
            j = i + 1
            while j < n and q[j] != '"':
                j += 1
            text = q[i + 1 : j]
            if text:
                tokens.append((text, True, negate))
            i = j + 1 if j < n else n
        else:
            j = i
            while j < n and not q[j].isspace() and q[j] != '"':
                j += 1
            text = q[i:j]
            if text:
                tokens.append((text, False, negate))
            i = j
    return tokens


def parse(q: str) -> list[list[Term]]:
    """Parse a query string into OR-groups of AND terms.

    Returns ``[]`` for empty / whitespace-only input or queries that
    reduce to no terms (e.g. ``"NOT"`` alone, ``"OR OR"``).
    """
    if not q or not q.strip():
        return []

    tokens = _tokenize(q)
    groups: list[list[Term]] = [[]]
    pending_not = False

    for text, is_phrase, neg_prefix in tokens:
        # OR / NOT keywords are only honored unquoted and without a `-` prefix
        # — `-OR` and `"OR"` are literal terms, not operators.
        if not is_phrase and not neg_prefix and text == "OR":
            if groups[-1]:
                groups.append([])
            pending_not = False
            continue
        if not is_phrase and not neg_prefix and text == "NOT":
            pending_not = True
            continue
        negate = neg_prefix or pending_not
        pending_not = False
        groups[-1].append(Term(text=text, negate=negate))

    return [g for g in groups if g]


def build_ilike_filter(
    groups: list[list[Term]],
    columns: Sequence[ColumnElement],
) -> ColumnElement | None:
    """Translate parser output into a SQLAlchemy boolean expression.

    For each AND-group: a positive term matches when at least one of the
    columns ILIKEs ``%text%``; a negated term matches when no column does.
    Groups are OR'd. Returns ``None`` if there is nothing to filter on
    (caller should skip ``query.filter``).

    Note: ``%`` and ``_`` in user input are passed through to the LIKE
    pattern as wildcards — same behavior as the prior single-term ILIKE.
    """
    if not groups or not columns:
        return None

    group_exprs = []
    for group in groups:
        term_exprs = []
        for term in group:
            pattern = f"%{term.text}%"
            # IS NOT NULL guard so SQL's three-valued logic doesn't drop rows
            # under negation: `NOT (NULL ILIKE p OR FALSE)` evaluates to NULL,
            # which `WHERE` treats as filtered-out.
            positive = or_(
                *(and_(col.is_not(None), col.ilike(pattern)) for col in columns)
            )
            term_exprs.append(not_(positive) if term.negate else positive)
        if term_exprs:
            group_exprs.append(and_(*term_exprs))

    if not group_exprs:
        return None
    return or_(*group_exprs)
