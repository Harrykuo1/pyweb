from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import Job, JobKind, PostStatus, User, UserRole


@pytest.fixture
def client_factory(db_session):
    db_session.add_all(
        [
            User(
                username="admin",
                password_hash=hash_password("admin-pw"),
                role=UserRole.ADMIN,
            ),
            User(
                username="viewer",
                password_hash=hash_password("viewer-pw"),
                role=UserRole.VIEWER,
            ),
        ]
    )
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def login_as(role):
        creds = {"admin": ("admin", "admin-pw"), "viewer": ("viewer", "viewer-pw")}[
            role
        ]
        r = client.post(
            "/api/auth/login", json={"username": creds[0], "password": creds[1]}
        )
        assert r.status_code == 200, r.text

    try:
        yield client, login_as
    finally:
        client.close()
        app.dependency_overrides.clear()


def _seed(db_session, rows):
    """rows = list of dicts; created_at offsets monotonically per index.

    Jobs default to ACCEPTED so a non-admin viewer can see them — the
    visibility filter (accepted + own) otherwise hides pending posts.
    """
    base = datetime(2025, 1, 1, tzinfo=UTC)
    for idx, row in enumerate(rows):
        db_session.add(
            Job(
                job_year=row.get("job_year", 2025),
                job_month=row.get("job_month", 6),
                company=row["company"],
                category=row.get("category"),
                kind=row.get("kind", JobKind.INTERNSHIP),
                experience_md=row.get("experience_md", "x"),
                real_name=row.get("real_name"),
                timeline_md=row.get("timeline_md"),
                status=row.get("status", PostStatus.ACCEPTED),
                is_anonymous=row.get("is_anonymous", False),
                subject_member_id=row.get("subject_member_id"),
                created_at=base.replace(day=1 + idx),
            )
        )
    db_session.commit()


# ---------- list / sort / filter / search ----------


def test_list_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/jobs")
    assert r.status_code == 401


def test_list_default_sort_created_at_desc(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme"},  # idx 0, oldest
            {"company": "Globex"},
            {"company": "Initech"},  # idx 2, newest
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert [x["company"] for x in body["items"]] == ["Initech", "Globex", "Acme"]


def test_list_sort_company_asc(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Globex"},
            {"company": "Acme"},
            {"company": "Initech"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?sort=company&order=asc")
    assert [x["company"] for x in r.json()["items"]] == ["Acme", "Globex", "Initech"]


def test_list_sort_job_year_desc(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "job_year": 2023},
            {"company": "B", "job_year": 2025},
            {"company": "C", "job_year": 2024},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?sort=job_year&order=desc")
    years = [x["job_year"] for x in r.json()["items"]]
    assert years == [2025, 2024, 2023]


def test_list_sort_real_name_anonymous_sinks(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "real_name": "Bob"},
            {"company": "B", "real_name": None},  # anonymous — should sink
            {"company": "C", "real_name": "Alice"},
            {"company": "D", "real_name": None},  # anonymous — should sink
        ],
    )
    login_as("viewer")

    r_asc = client.get("/api/jobs?sort=real_name&order=asc")
    names_asc = [x["display_name"] for x in r_asc.json()["items"]]
    assert names_asc[:2] == ["Alice", "Bob"]
    assert names_asc[2:] == [None, None]

    r_desc = client.get("/api/jobs?sort=real_name&order=desc")
    names_desc = [x["display_name"] for x in r_desc.json()["items"]]
    assert names_desc[:2] == ["Bob", "Alice"]
    assert names_desc[2:] == [None, None]


def test_list_sort_kind_asc_groups_internships_first(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            # idx 0..3 — created_at runs 1/1, 1/2, 1/3, 1/4
            {"company": "F1", "kind": JobKind.FULLTIME},
            {"company": "I1", "kind": JobKind.INTERNSHIP},
            {"company": "F2", "kind": JobKind.FULLTIME},
            {"company": "I2", "kind": JobKind.INTERNSHIP},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?sort=kind&order=asc")
    items = r.json()["items"]
    # Internships first; within each kind, newest-first by created_at.
    assert [(x["kind"], x["company"]) for x in items] == [
        ("internship", "I2"),
        ("internship", "I1"),
        ("fulltime", "F2"),
        ("fulltime", "F1"),
    ]


def test_list_sort_kind_desc_groups_fulltime_first(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "F1", "kind": JobKind.FULLTIME},
            {"company": "I1", "kind": JobKind.INTERNSHIP},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?sort=kind&order=desc")
    items = r.json()["items"]
    assert [x["kind"] for x in items] == ["fulltime", "internship"]


def test_list_filter_by_year(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "job_year": 2024},
            {"company": "B", "job_year": 2025},
            {"company": "C", "job_year": 2024},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?year=2024")
    assert r.json()["total"] == 2


def test_list_filter_by_company_exact_match(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme"},
            {"company": "Acme Inc"},
            {"company": "Globex"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?company=Acme")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["company"] == "Acme"


def test_list_filter_by_company_multi_or(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme"},
            {"company": "Globex"},
            {"company": "Initech"},
            {"company": "Other"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?company=Acme&company=Globex")
    body = r.json()
    assert body["total"] == 2
    assert sorted(x["company"] for x in body["items"]) == ["Acme", "Globex"]


def test_list_filter_by_kind_internship(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "kind": JobKind.INTERNSHIP},
            {"company": "B", "kind": JobKind.FULLTIME},
            {"company": "C", "kind": JobKind.INTERNSHIP},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?kind=internship")
    body = r.json()
    assert body["total"] == 2
    assert all(x["kind"] == "internship" for x in body["items"])


def test_list_filter_by_kind_fulltime(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "kind": JobKind.INTERNSHIP},
            {"company": "B", "kind": JobKind.FULLTIME},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?kind=fulltime")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["kind"] == "fulltime"


def test_list_filter_kind_rejects_invalid_value(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/jobs?kind=part-time")
    assert r.status_code == 422


def test_list_search_q_matches_real_name_and_experience(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme", "experience_md": "interview was tough"},
            {"company": "Globex", "real_name": "interview-fan", "experience_md": "x"},
            {"company": "Other", "experience_md": "system design"},
        ],
    )
    # Admin search covers real_name too; the §8 restriction (non-admins
    # cannot search real_name) is asserted in test_jobs_visibility.py.
    login_as("admin")

    r = client.get("/api/jobs?q=interview")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["Acme", "Globex"]


def test_list_search_q_does_not_match_company_name(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme", "real_name": "alice", "experience_md": "fine"},
            {"company": "Other", "real_name": "Acme person", "experience_md": "x"},
        ],
    )
    login_as("admin")  # admin search includes real_name (see §8 test elsewhere)

    r = client.get("/api/jobs?q=Acme")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["Other"]


def test_list_combined_filter_and_search(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {
                "company": "Acme",
                "job_year": 2024,
                "experience_md": "interview",
                "kind": JobKind.INTERNSHIP,
            },
            {
                "company": "Acme",
                "job_year": 2025,
                "experience_md": "interview",
                "kind": JobKind.FULLTIME,
            },
            {"company": "Globex", "job_year": 2024, "experience_md": "interview"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?company=Acme&year=2024&q=interview&kind=internship")
    body = r.json()
    assert body["total"] == 1


def test_list_search_q_implicit_and_two_terms(client_factory, db_session):
    # Both terms must appear; either field is fine for either term.
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Has-both", "experience_md": "senior react work"},
            {"company": "Only-senior", "experience_md": "senior backend"},
            {"company": "Only-react", "real_name": "react-fan", "experience_md": "x"},
            {
                "company": "Cross-fields",
                "real_name": "senior person",
                "experience_md": "react notes",
            },
        ],
    )
    login_as("admin")  # admin search includes real_name (see §8 test elsewhere)

    r = client.get("/api/jobs?q=senior react")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["Cross-fields", "Has-both"]


def test_list_search_q_or_groups(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "experience_md": "react notes"},
            {"company": "B", "experience_md": "vue notes"},
            {"company": "C", "experience_md": "go notes"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?q=react OR vue")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["A", "B"]


def test_list_search_q_dash_excludes(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Senior-only", "experience_md": "senior react"},
            {"company": "Senior+junior", "experience_md": "senior react junior"},
            {"company": "Junior-only", "experience_md": "junior react"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?q=react -junior")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["Senior-only"]


def test_list_search_q_not_keyword_excludes(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "experience_md": "team lead role"},
            {"company": "B", "experience_md": "team member role"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?q=team NOT lead")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["B"]


def test_list_search_q_quoted_phrase_preserves_whitespace(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Match", "experience_md": "promoted to team lead in 2024"},
            {"company": "Wrong-order", "experience_md": "the lead of the team"},
            {"company": "Tokens-only", "experience_md": "led the team and was a lead"},
        ],
    )
    login_as("viewer")

    r = client.get('/api/jobs?q="team lead"')
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["Match"]


def test_list_search_q_combined_boolean_query(client_factory, db_session):
    # `senior react OR vue -junior "team lead"` (Google-style):
    # (senior AND react) OR (vue AND NOT junior AND "team lead")
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "G1-hit", "experience_md": "senior react work"},
            {
                "company": "G1-also-junior",
                "experience_md": "senior react junior",
            },  # still hits G1
            {"company": "G2-hit", "experience_md": "vue role, team lead"},
            {
                "company": "G2-junior",
                "experience_md": "vue role, team lead, junior",
            },  # excluded
            {
                "company": "G2-no-phrase",
                "experience_md": "vue role, the lead of the team",
            },  # phrase missing
            {"company": "Neither", "experience_md": "go backend"},
        ],
    )
    login_as("viewer")

    r = client.get('/api/jobs?q=senior react OR vue -junior "team lead"')
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["G1-also-junior", "G1-hit", "G2-hit"]


def test_list_search_q_single_term_remains_substring(client_factory, db_session):
    # Backwards-compatible with the old single-term ILIKE behavior.
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "experience_md": "interview tips"},
            {"company": "B", "experience_md": "system design"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?q=interview")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["A"]


def test_list_search_q_still_excludes_company_field(client_factory, db_session):
    # Company is filtered via the multi-select picker, not q.
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme", "real_name": "alice", "experience_md": "x"},
            {"company": "Other", "real_name": "bob", "experience_md": "y"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?q=Acme")
    assert r.json()["items"] == []


def test_list_rejects_invalid_sort(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/jobs?sort=garbage")
    assert r.status_code == 422


# ---------- companies autocomplete ----------


def test_companies_autocomplete_distinct(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme"},
            {"company": "Acme"},  # dup
            {"company": "Globex"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs/companies")
    assert r.status_code == 200
    assert r.json() == ["Acme", "Globex"]


def test_list_filter_by_category_single(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "category": "Backend"},
            {"company": "B", "category": "DevOps"},
            {"company": "C", "category": None},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?category=Backend")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["A"]


def test_list_filter_by_category_multi_or(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "category": "Backend"},
            {"company": "B", "category": "DevOps"},
            {"company": "C", "category": "R&D"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?category=Backend&category=DevOps")
    companies = sorted(x["company"] for x in r.json()["items"])
    assert companies == ["A", "B"]


def test_list_filter_by_category_excludes_null(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "A", "category": "Backend"},
            {"company": "B", "category": None},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?category=Backend")
    assert sorted(x["company"] for x in r.json()["items"]) == ["A"]


def test_list_filter_by_category_combined_with_company(client_factory, db_session):
    # Filters compose with AND across orthogonal facets.
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme", "category": "Backend"},
            {"company": "Acme", "category": "DevOps"},
            {"company": "Globex", "category": "Backend"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs?company=Acme&category=Backend")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["company"] == "Acme"
    assert items[0]["category"] == "Backend"


def test_categories_autocomplete_distinct_skips_nulls(client_factory, db_session):
    client, login_as = client_factory
    db_session.add_all(
        [
            Job(
                job_year=2025,
                job_month=1,
                company="A",
                category="Backend",
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),
            Job(
                job_year=2025,
                job_month=2,
                company="B",
                category="Backend",
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),  # dup
            Job(
                job_year=2025,
                job_month=3,
                company="C",
                category="DevOps",
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),
            Job(
                job_year=2025,
                job_month=4,
                company="D",
                category=None,
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),
        ]
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/jobs/categories")
    assert r.status_code == 200
    assert r.json() == ["Backend", "DevOps"]


def test_categories_autocomplete_prefix(client_factory, db_session):
    client, login_as = client_factory
    db_session.add_all(
        [
            Job(
                job_year=2025,
                job_month=1,
                company="A",
                category="Backend",
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),
            Job(
                job_year=2025,
                job_month=2,
                company="B",
                category="DevOps",
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),
            Job(
                job_year=2025,
                job_month=3,
                company="C",
                category="Data",
                kind=JobKind.INTERNSHIP,
                experience_md="x",
            ),
        ]
    )
    db_session.commit()
    login_as("viewer")

    r = client.get("/api/jobs/categories?prefix=de")
    # ILIKE so prefix is case-insensitive.
    assert r.json() == ["DevOps"]


def test_categories_autocomplete_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/jobs/categories")
    assert r.status_code == 401


def test_companies_autocomplete_prefix(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [
            {"company": "Acme"},
            {"company": "Acme Inc"},
            {"company": "Globex"},
        ],
    )
    login_as("viewer")

    r = client.get("/api/jobs/companies?prefix=ac")
    assert r.json() == ["Acme", "Acme Inc"]


def test_companies_autocomplete_requires_auth(client_factory):
    client, _ = client_factory
    r = client.get("/api/jobs/companies")
    assert r.status_code == 401


# ---------- detail ----------


def test_get_job_404(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.get("/api/jobs/9999")
    assert r.status_code == 404


def test_get_job_returns_full_markdown(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme", "experience_md": "## interview"}])
    login_as("viewer")

    r = client.get("/api/jobs/1")
    assert r.status_code == 200
    body = r.json()
    assert body["experience_md"] == "## interview"
    assert body["kind"] == "internship"


# ---------- create ----------


def test_create_internship_job_admin_succeeds(client_factory):
    client, login_as = client_factory
    login_as("admin")
    payload = {
        "job_year": 2025,
        "job_month": 6,
        "company": "Acme",
        "kind": "internship",
        "experience_md": "## interview",
        "real_name": "Carol",
    }
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["company"] == "Acme"
    assert body["kind"] == "internship"
    assert body["job_month"] == 6
    assert body["created_at"] is not None


def test_create_with_category_round_trips(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "category": "DevOps",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "DevOps"


def test_create_without_category_returns_null(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["category"] is None


def test_create_fulltime_job_admin_succeeds(client_factory):
    client, login_as = client_factory
    login_as("admin")
    payload = {
        "job_year": 2025,
        "job_month": 11,
        "company": "Globex",
        "kind": "fulltime",
        "experience_md": "## offer",
    }
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "fulltime"


def test_create_rejects_missing_kind(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={"job_year": 2025, "company": "Acme", "experience_md": "x"},
    )
    assert r.status_code == 422


def test_create_rejects_invalid_kind(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "company": "Acme",
            "kind": "freelance",
            "experience_md": "x",
        },
    )
    assert r.status_code == 422


def test_create_viewer_403(client_factory):
    client, login_as = client_factory
    login_as("viewer")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 403


def test_create_unauth_401(client_factory):
    client, _ = client_factory
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 401


def test_create_rejects_year_below_min(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 1999,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 422


def test_create_rejects_year_above_max(client_factory):
    client, login_as = client_factory
    login_as("admin")
    far_future = datetime.now(UTC).year + 5
    r = client.post(
        "/api/jobs",
        json={
            "job_year": far_future,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 422


# ---------- update ----------


def test_update_admin_partial(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Old", "experience_md": "x"}])
    login_as("admin")

    r = client.put("/api/jobs/1", json={"company": "New"})
    assert r.status_code == 200
    body = r.json()
    assert body["company"] == "New"
    assert body["experience_md"] == "x"  # unchanged


def test_update_kind_admin_promotes_internship_to_fulltime(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme", "kind": JobKind.INTERNSHIP}])
    login_as("admin")

    r = client.put("/api/jobs/1", json={"kind": "fulltime"})
    assert r.status_code == 200
    assert r.json()["kind"] == "fulltime"


def test_update_kind_rejects_invalid_value(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("admin")

    r = client.put("/api/jobs/1", json={"kind": "freelance"})
    assert r.status_code == 422


def test_update_viewer_403(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("viewer")
    r = client.put("/api/jobs/1", json={"company": "Hack"})
    assert r.status_code == 403


def test_update_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.put("/api/jobs/9999", json={"company": "X"})
    assert r.status_code == 404


# ---------- timeline_events ----------


def _as_stored(events):
    """Input entries as the response returns them.

    An entry now carries either a date or a day_offset, so the field the
    caller left out comes back explicitly null rather than being absent.
    """
    return [{"date": None, "day_offset": None, **e} for e in events]


def test_create_with_timeline_events_round_trips(client_factory):
    client, login_as = client_factory
    login_as("admin")
    events = [
        {"date": "2025-02-23", "event": "投遞履歷"},
        {"date": "2025-03-06", "event": "面試邀請"},
        {"date": "2025-04-17", "event": "拿到 offer"},
    ]
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": events,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["timeline_events"] == _as_stored(events)


def test_create_with_cross_year_timeline_events(client_factory):
    # The whole reason the schema records full ISO dates instead of
    # month + day is to handle recruitment processes that span the
    # year boundary cleanly. Verify a Dec → Jan timeline round-trips.
    client, login_as = client_factory
    login_as("admin")
    events = [
        {"date": "2025-12-15", "event": "投遞履歷"},
        {"date": "2026-01-08", "event": "面試"},
        {"date": "2026-02-03", "event": "拿到 offer"},
    ]
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2026,
            "job_month": 2,
            "company": "Acme",
            "kind": "fulltime",
            "experience_md": "x",
            "timeline_events": events,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["timeline_events"] == _as_stored(events)


def test_create_without_timeline_events_returns_null(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["timeline_events"] is None


def test_create_with_empty_timeline_events_list_round_trips(client_factory):
    # An empty list should be accepted and stored as an empty list, not
    # coerced to null — the editor can produce this when admin starts a
    # timeline and immediately deletes all rows.
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": [],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["timeline_events"] == []


def test_create_rejects_timeline_event_with_invalid_date(client_factory):
    # Pydantic's date type rejects malformed strings and impossible
    # dates (e.g. Feb 30) automatically — assert both paths.
    client, login_as = client_factory
    login_as("admin")
    for bad in ("2025-13-01", "2025-02-30", "not-a-date"):
        r = client.post(
            "/api/jobs",
            json={
                "job_year": 2025,
                "job_month": 4,
                "company": "Acme",
                "kind": "internship",
                "experience_md": "x",
                "timeline_events": [{"date": bad, "event": "x"}],
            },
        )
        assert r.status_code == 422, (
            f"expected 422 for date={bad!r}, got {r.status_code}"
        )


def test_create_rejects_timeline_event_with_blank_text(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": [{"date": "2025-02-23", "event": ""}],
        },
    )
    assert r.status_code == 422


def test_create_rejects_too_many_timeline_events(client_factory):
    client, login_as = client_factory
    login_as("admin")
    too_many = [{"date": "2025-01-01", "event": "e"} for _ in range(51)]
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": too_many,
        },
    )
    assert r.status_code == 422


def test_update_replaces_timeline_events(client_factory, db_session):
    # PUT semantics: sending a new list overwrites the previous one.
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme", "experience_md": "x"}])
    login_as("admin")

    first = [{"date": "2025-02-01", "event": "a"}]
    second = [
        {"date": "2025-03-05", "event": "b"},
        {"date": "2025-04-10", "event": "c"},
    ]

    r1 = client.put("/api/jobs/1", json={"timeline_events": first})
    assert r1.status_code == 200
    assert r1.json()["timeline_events"] == _as_stored(first)

    r2 = client.put("/api/jobs/1", json={"timeline_events": second})
    assert r2.status_code == 200
    assert r2.json()["timeline_events"] == _as_stored(second)


def test_update_clears_timeline_events_with_null(client_factory, db_session):
    client, login_as = client_factory
    _seed(
        db_session,
        [{"company": "Acme", "experience_md": "x"}],
    )
    login_as("admin")
    client.put(
        "/api/jobs/1",
        json={"timeline_events": [{"date": "2025-02-01", "event": "a"}]},
    )

    r = client.put("/api/jobs/1", json={"timeline_events": None})
    assert r.status_code == 200
    assert r.json()["timeline_events"] is None


def test_legacy_timeline_md_and_new_timeline_events_are_independent(
    client_factory, db_session
):
    # Old jobs only have timeline_md; new jobs use timeline_events.
    # Setting one must not silently clear the other so the viewer's
    # "fall back to legacy markdown" path stays predictable.
    client, login_as = client_factory
    _seed(
        db_session,
        [{"company": "Acme", "experience_md": "x", "timeline_md": "- 投遞 2/23"}],
    )
    login_as("admin")

    r = client.put(
        "/api/jobs/1",
        json={"timeline_events": [{"date": "2025-02-23", "event": "投遞"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["timeline_md"] == "- 投遞 2/23"
    assert body["timeline_events"] == _as_stored(
        [{"date": "2025-02-23", "event": "投遞"}]
    )


# ---------- delete ----------


def test_delete_admin_with_correct_password(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("admin")

    r = client.request(
        "DELETE",
        "/api/jobs/1",
        json={"password": "admin-pw"},
    )
    assert r.status_code == 204
    assert client.get("/api/jobs/1").status_code == 404


def test_delete_wrong_password_returns_422(client_factory, db_session):
    # 422 (not 401) so the frontend's global session-expired interceptor
    # doesn't bounce the user back to /login — the session is still
    # valid, only the body-supplied password is wrong.
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("admin")

    r = client.request(
        "DELETE",
        "/api/jobs/1",
        json={"password": "nope"},
    )
    assert r.status_code == 422
    assert client.get("/api/jobs/1").status_code == 200


def test_delete_missing_password_422(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("admin")
    r = client.delete("/api/jobs/1")
    assert r.status_code == 422


def test_delete_viewer_403(client_factory, db_session):
    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("viewer")
    r = client.request(
        "DELETE",
        "/api/jobs/1",
        json={"password": "viewer-pw"},
    )
    assert r.status_code == 403


def test_delete_404(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.request(
        "DELETE",
        "/api/jobs/9999",
        json={"password": "admin-pw"},
    )
    assert r.status_code == 404


def test_delete_removes_on_disk_uploads_dir(client_factory, db_session, tmp_path):
    """DB cascades clean job_attachments rows, but the on-disk
    uploads/jobs/{id}/ tree was previously leaked. Verify the
    directory and any files inside (originals + preview PDFs) are
    swept up alongside the row delete."""
    from app.routers.job_attachments import get_uploads_root

    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("admin")

    uploads_dir = tmp_path / "uploads"
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir

    # Seed an on-disk layout that mimics what a real upload produces:
    # nested folder relpath + an OnlyOffice preview PDF sibling.
    job_dir = uploads_dir / "jobs" / "1"
    (job_dir / "src" / "components").mkdir(parents=True)
    (job_dir / "src" / "components" / "deck.pptx").write_bytes(b"PK\x03\x04")
    (job_dir / "src" / "components" / "deck.pptx.preview.pdf").write_bytes(b"%PDF-1.4")

    try:
        r = client.request(
            "DELETE",
            "/api/jobs/1",
            json={"password": "admin-pw"},
        )
        assert r.status_code == 204
        assert not job_dir.exists()
        # Parent uploads/jobs/ stays — it's shared across jobs and
        # rmtree only targets the specific job's directory.
        assert (uploads_dir / "jobs").exists()
    finally:
        app.dependency_overrides.pop(get_uploads_root, None)


def test_get_reports_attachment_count(client_factory, db_session):
    """Detail dialog hides the 附件 tab when attachment_count is 0,
    so the field has to be present on both list and get responses."""
    from app.models import JobAttachment

    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}, {"company": "Beta"}])
    # Two attachments on job 1, zero on job 2.
    db_session.add_all(
        [
            JobAttachment(
                job_id=1,
                filename="a.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                uploaded_at=datetime(2026, 5, 1, tzinfo=UTC),
            ),
            JobAttachment(
                job_id=1,
                filename="b.pdf",
                mime_type="application/pdf",
                size_bytes=1,
                uploaded_at=datetime(2026, 5, 2, tzinfo=UTC),
            ),
        ]
    )
    db_session.commit()
    login_as("viewer")

    r1 = client.get("/api/jobs/1").json()
    r2 = client.get("/api/jobs/2").json()
    assert r1["attachment_count"] == 2
    assert r2["attachment_count"] == 0

    listing = client.get("/api/jobs").json()
    by_id = {row["id"]: row["attachment_count"] for row in listing["items"]}
    assert by_id == {1: 2, 2: 0}


def test_create_reports_zero_attachment_count(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "kind": "internship",
            "job_year": 2026,
            "job_month": 5,
            "company": "Acme",
            "experience_md": "hi",
        },
    )
    assert r.status_code == 201
    assert r.json()["attachment_count"] == 0


def test_delete_succeeds_when_no_uploads_dir_exists(
    client_factory, db_session, tmp_path
):
    """Most jobs never get an attachment so uploads/jobs/{id}/ may
    never exist on disk at delete time. rmtree(ignore_errors=True)
    must no-op rather than 500 the delete."""
    from app.routers.job_attachments import get_uploads_root

    client, login_as = client_factory
    _seed(db_session, [{"company": "Acme"}])
    login_as("admin")

    uploads_dir = tmp_path / "uploads"
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    try:
        r = client.request(
            "DELETE",
            "/api/jobs/1",
            json={"password": "admin-pw"},
        )
        assert r.status_code == 204
    finally:
        app.dependency_overrides.pop(get_uploads_root, None)


def test_create_with_relative_timeline_events_round_trips(client_factory):
    """A process recalled from memory records as offsets and stays that way —
    nothing derives a date for it, because that would be a guess on record."""
    client, login_as = client_factory
    login_as("admin")
    events = [
        {"day_offset": 0, "event": "投遞履歷"},
        {"day_offset": 7, "event": "線上測驗"},
        {"day_offset": 21, "event": "拿到 offer"},
    ]
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": events,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["timeline_events"] == _as_stored(events)


def test_create_with_a_mix_of_dated_and_relative_entries(client_factory):
    # The common shape: the date of applying is on record, the rest is
    # remembered only as "about a week later".
    client, login_as = client_factory
    login_as("admin")
    events = [
        {"date": "2025-03-01", "event": "投遞履歷"},
        {"day_offset": 7, "event": "線上測驗"},
        {"date": "2025-04-17", "event": "拿到 offer"},
    ]
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": events,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["timeline_events"] == _as_stored(events)


def test_a_timeline_entry_with_no_position_is_rejected(client_factory):
    client, login_as = client_factory
    login_as("admin")
    r = client.post(
        "/api/jobs",
        json={
            "job_year": 2025,
            "job_month": 4,
            "company": "Acme",
            "kind": "internship",
            "experience_md": "x",
            "timeline_events": [{"event": "投遞履歷"}],
        },
    )
    assert r.status_code == 422
