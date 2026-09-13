from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models import (
    AppConfig,
    Event,
    EventVideo,
    Member,
    PostStatus,
    User,
    UserRole,
    VideoKind,
    VideoStatus,
)
from app.routers.event_videos import get_uploads_root


@pytest.fixture
def uploads_dir(tmp_path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture
def ctx(db_session, uploads_dir):
    """An accepted event owned by `author`, plus a member who is not its owner."""
    admin = User(
        username="admin", password_hash=hash_password("admin-pw"), role=UserRole.ADMIN
    )
    author = User(
        username="author",
        password_hash=hash_password("author-pw"),
        role=UserRole.MEMBER,
    )
    other = User(
        username="other", password_hash=hash_password("other-pw"), role=UserRole.MEMBER
    )
    db_session.add_all([admin, author, other])
    db_session.flush()
    db_session.add_all(
        [
            Member(
                graduation_year=2024,
                real_name="作者",
                institution="X",
                user_id=author.id,
            ),
            Member(
                graduation_year=2024,
                real_name="別人",
                institution="Y",
                user_id=other.id,
            ),
        ]
    )
    event = Event(
        id=1,
        title="運動會",
        event_date=date(2026, 5, 1),
        author_user_id=author.id,
        status=PostStatus.ACCEPTED,
    )
    db_session.add(event)
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_uploads_root] = lambda: uploads_dir
    client = TestClient(app)

    def login(pw):
        assert client.post("/api/auth/login", json={"password": pw}).status_code == 200

    try:
        yield client, login, event
    finally:
        client.close()
        app.dependency_overrides.clear()


def _upload(client, *, data=b"fake-video-bytes", mime="video/mp4", name="clip.mp4"):
    return client.post(
        "/api/events/1/videos",
        files={"file": (name, BytesIO(data), mime)},
    )


def _stub_transcode(monkeypatch, db, uploads_dir, *, fail=False):
    """Stand in for ffmpeg, which does not exist on a dev host.

    The real one opens its own SessionLocal — correct for a background task,
    but it would reach past the in-memory database these tests run against,
    so the stub works through the test's session instead. What is under test
    here is the router's half of the contract; the background task's own
    session handling is exercised against the container.
    """
    calls = {}

    def fake(video_id, source, uploads_root):
        calls["source_existed"] = source.exists()
        from app.core.event_media import event_uploads_dir

        video = db.query(EventVideo).filter_by(id=video_id).one()
        if fail:
            video.status = VideoStatus.FAILED
            video.failed_at = datetime.now(UTC)
            video.error_detail = "Invalid data found when processing input"
        else:
            event_dir = event_uploads_dir(uploads_root, video.event_id)
            event_dir.mkdir(parents=True, exist_ok=True)
            (event_dir / f"{video_id}.mp4").write_bytes(b"mp4")
            (event_dir / f"{video_id}.jpg").write_bytes(b"jpg")
            video.filename = f"{video_id}.mp4"
            video.poster_filename = f"{video_id}.jpg"
            video.size_bytes = 3
            video.duration_seconds = 12
            video.status = VideoStatus.READY
        db.commit()
        source.unlink(missing_ok=True)

    monkeypatch.setattr("app.routers.event_videos.transcode_in_background", fake)
    return calls


def test_upload_returns_processing_immediately(
    ctx, db_session, monkeypatch, uploads_dir
):
    # Transcoding takes about as long as the clip itself, so the response
    # cannot wait for it — the row comes back mid-flight and the client polls.
    client, login, _ = ctx
    _stub_transcode(monkeypatch, db_session, uploads_dir)
    login("author-pw")

    r = _upload(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "processing"
    assert body["kind"] == "upload"
    assert body["youtube_id"] is None


def test_non_video_is_rejected(ctx, db_session, monkeypatch, uploads_dir):
    client, login, _ = ctx
    _stub_transcode(monkeypatch, db_session, uploads_dir)
    login("author-pw")
    r = _upload(client, mime="application/pdf", name="doc.pdf")
    assert r.status_code == 415


def test_a_member_who_is_not_the_author_cannot_upload(
    ctx, db_session, monkeypatch, uploads_dir
):
    client, login, _ = ctx
    _stub_transcode(monkeypatch, db_session, uploads_dir)
    login("other-pw")
    assert _upload(client).status_code == 403


def test_oversized_video_is_rejected_and_leaves_nothing(
    ctx, db_session, uploads_dir, monkeypatch
):
    client, login, _ = ctx
    _stub_transcode(monkeypatch, db_session, uploads_dir)
    db_session.add(AppConfig(key="max_video_mb", value="0"))
    db_session.commit()
    login("author-pw")

    assert _upload(client).status_code == 413
    assert db_session.query(EventVideo).count() == 0
    event_dir = uploads_dir / "events" / "1"
    assert (list(event_dir.iterdir()) if event_dir.exists() else []) == []


def test_failed_videos_do_not_consume_the_per_event_limit(
    ctx, db_session, monkeypatch, uploads_dir
):
    """A failed row holds no video. Counting it would let a few bad uploads
    lock someone out of a limit they never actually used."""
    client, login, event = ctx
    db_session.add(AppConfig(key="max_videos_per_event", value="1"))
    db_session.add(
        EventVideo(
            event_id=event.id,
            kind=VideoKind.UPLOAD,
            status=VideoStatus.FAILED,
            failed_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    _stub_transcode(monkeypatch, db_session, uploads_dir)
    login("author-pw")

    assert _upload(client).status_code == 201

    # A ready one does count, so the next upload is refused.
    db_session.query(EventVideo).filter_by(status=VideoStatus.PROCESSING).update(
        {"status": VideoStatus.READY}
    )
    db_session.commit()
    assert _upload(client).status_code == 409


def test_failed_videos_are_hidden_from_everyone_but_the_owner(
    ctx, db_session, monkeypatch, uploads_dir
):
    client, login, event = ctx
    db_session.add(
        EventVideo(
            event_id=event.id,
            kind=VideoKind.UPLOAD,
            status=VideoStatus.FAILED,
            failed_at=datetime.now(UTC),
            error_detail="ffmpeg said no",
        )
    )
    db_session.commit()

    login("other-pw")
    assert client.get("/api/events/1/videos").json() == []

    login("author-pw")
    rows = client.get("/api/events/1/videos").json()
    assert len(rows) == 1
    # The author is told it failed but not in ffmpeg's words.
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_detail"] is None

    login("admin-pw")
    rows = client.get("/api/events/1/videos").json()
    assert rows[0]["error_detail"] == "ffmpeg said no"


def test_file_is_not_served_until_the_transcode_finishes(ctx, db_session):
    client, login, event = ctx
    video = EventVideo(
        event_id=event.id, kind=VideoKind.UPLOAD, status=VideoStatus.PROCESSING
    )
    db_session.add(video)
    db_session.commit()

    login("author-pw")
    assert client.get(f"/api/events/1/videos/{video.id}/file").status_code == 404


def test_delete_removes_the_row_and_every_file_it_owns(
    ctx, db_session, uploads_dir, monkeypatch
):
    client, login, event = ctx
    _stub_transcode(monkeypatch, db_session, uploads_dir)
    login("author-pw")
    vid = _upload(client).json()["id"]

    event_dir = uploads_dir / "events" / "1"
    event_dir.mkdir(parents=True, exist_ok=True)
    for name in (f"{vid}.mp4", f"{vid}.jpg", f"{vid}.src"):
        (event_dir / name).write_bytes(b"x")
    db_session.query(EventVideo).filter_by(id=vid).update(
        {"filename": f"{vid}.mp4", "poster_filename": f"{vid}.jpg"}
    )
    db_session.commit()

    # The author owns the event, so no password — same rule as photos.
    assert client.delete(f"/api/events/1/videos/{vid}").status_code == 204
    assert db_session.query(EventVideo).count() == 0
    # Including the staging upload, which is the copy worth hundreds of MB.
    assert list(event_dir.iterdir()) == []


def test_a_youtube_link_is_stored_as_an_id_and_is_ready_at_once(ctx, db_session):
    """Nothing to transcode, so it is watchable the moment it is saved — and
    only the id survives, never the URL that was pasted."""
    client, login, _ = ctx
    login("author-pw")

    r = client.post(
        "/api/events/1/videos/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "youtube"
    assert body["status"] == "ready"
    assert body["youtube_id"] == "dQw4w9WgXcQ"

    row = db_session.query(EventVideo).one()
    assert row.youtube_id == "dQw4w9WgXcQ"
    # A YouTube row owns no file; the CHECK constraint depends on this.
    assert row.filename is None


@pytest.mark.parametrize(
    "label,url",
    [
        ("a javascript scheme", "javascript:alert(1)"),
        ("a lookalike host", "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ"),
        ("not a video page", "https://www.youtube.com/@someone"),
    ],
)
def test_anything_that_is_not_a_youtube_video_is_refused(ctx, db_session, label, url):
    client, login, _ = ctx
    login("author-pw")
    r = client.post("/api/events/1/videos/youtube", json={"url": url})
    assert r.status_code == 422, label
    assert db_session.query(EventVideo).count() == 0


def test_youtube_links_share_the_per_event_video_limit(ctx, db_session):
    # One limit covers both kinds: to a viewer they are the same thing on
    # the page, whatever the storage costs behind it.
    client, login, _ = ctx
    db_session.add(AppConfig(key="max_videos_per_event", value="1"))
    db_session.commit()
    login("author-pw")

    first = client.post(
        "/api/events/1/videos/youtube",
        json={"url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/events/1/videos/youtube",
        json={"url": "https://youtu.be/oHg5SJYRHA0"},
    )
    assert second.status_code == 409


def test_a_member_who_is_not_the_author_cannot_add_a_link(ctx):
    client, login, _ = ctx
    login("other-pw")
    r = client.post(
        "/api/events/1/videos/youtube",
        json={"url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert r.status_code == 403


def test_an_admin_must_confirm_a_video_deletion_with_the_password(ctx, db_session):
    """Photos and videos sit in one grid with one delete button each, so the
    two cannot ask for different things."""
    client, login, event = ctx
    video = EventVideo(
        event_id=event.id,
        kind=VideoKind.YOUTUBE,
        status=VideoStatus.READY,
        youtube_id="dQw4w9WgXcQ",
    )
    db_session.add(video)
    db_session.commit()

    login("admin-pw")
    assert client.delete(f"/api/events/1/videos/{video.id}").status_code == 422

    r = client.request(
        "DELETE",
        f"/api/events/1/videos/{video.id}",
        json={"password": "admin-pw"},
    )
    assert r.status_code == 204
    assert db_session.query(EventVideo).count() == 0


def _photo_row(db, event_id, n, order=0):
    from app.models import EventPhoto

    row = EventPhoto(
        event_id=event_id,
        filename=f"{n}.jpg",
        mime_type="image/jpeg",
        size_bytes=1,
        sort_order=order,
    )
    db.add(row)
    db.flush()
    return row


def _order(db, event_id):
    """The merged order the grid would render."""
    from app.models import EventPhoto

    rows = [
        ("photo", p.id, p.sort_order)
        for p in db.query(EventPhoto).filter_by(event_id=event_id)
    ] + [
        ("video", v.id, v.sort_order)
        for v in db.query(EventVideo).filter_by(event_id=event_id)
    ]
    return [(k, i) for k, i, _ in sorted(rows, key=lambda r: (r[2], r[0], r[1]))]


def test_reorder_interleaves_photos_and_videos(ctx, db_session):
    """The two tables hold one sequence, so a position has to be able to put
    a video between two photos."""
    client, login, event = ctx
    p1 = _photo_row(db_session, event.id, 1)
    p2 = _photo_row(db_session, event.id, 2)
    video = EventVideo(
        event_id=event.id,
        kind=VideoKind.YOUTUBE,
        status=VideoStatus.READY,
        youtube_id="dQw4w9WgXcQ",
    )
    db_session.add(video)
    db_session.commit()

    login("author-pw")
    r = client.put(
        "/api/events/1/media/order",
        json={
            "items": [
                {"type": "photo", "id": p1.id},
                {"type": "video", "id": video.id},
                {"type": "photo", "id": p2.id},
            ]
        },
    )
    assert r.status_code == 204, r.text
    assert _order(db_session, event.id) == [
        ("photo", p1.id),
        ("video", video.id),
        ("photo", p2.id),
    ]


def test_media_the_client_did_not_know_about_lands_after_the_listed_items(
    ctx, db_session
):
    """Something uploaded between the client's read and its write must end up
    after everything ordered, not wherever its old number happens to fall.

    The unlisted row starts at sort_order 0, the same value the first listed
    item is about to be given — so leaving it alone would put it second,
    decided by a tiebreaker rather than by anything the user asked for.
    """
    client, login, event = ctx
    p1 = _photo_row(db_session, event.id, 1, order=5)
    p2 = _photo_row(db_session, event.id, 2, order=6)
    unseen = EventVideo(
        event_id=event.id,
        kind=VideoKind.YOUTUBE,
        status=VideoStatus.READY,
        youtube_id="dQw4w9WgXcQ",
        sort_order=0,
    )
    db_session.add(unseen)
    db_session.commit()

    login("author-pw")
    r = client.put(
        "/api/events/1/media/order",
        json={
            "items": [
                {"type": "photo", "id": p2.id},
                {"type": "photo", "id": p1.id},
            ]
        },
    )
    assert r.status_code == 204
    assert _order(db_session, event.id) == [
        ("photo", p2.id),
        ("photo", p1.id),
        ("video", unseen.id),
    ]


def test_reorder_rejects_media_from_another_event(ctx, db_session):
    client, login, event = ctx
    from app.models import Event

    other = Event(
        id=2, title="另一場", event_date=event.event_date, status=PostStatus.ACCEPTED
    )
    db_session.add(other)
    db_session.flush()
    foreign = _photo_row(db_session, other.id, 1)
    db_session.commit()

    login("author-pw")
    r = client.put(
        "/api/events/1/media/order",
        json={"items": [{"type": "photo", "id": foreign.id}]},
    )
    assert r.status_code == 404


def test_reorder_rejects_a_duplicated_item(ctx, db_session):
    # Two positions for one row would make the resulting order depend on
    # iteration order rather than on what the client asked for.
    client, login, event = ctx
    p1 = _photo_row(db_session, event.id, 1)
    db_session.commit()

    login("author-pw")
    r = client.put(
        "/api/events/1/media/order",
        json={
            "items": [
                {"type": "photo", "id": p1.id},
                {"type": "photo", "id": p1.id},
            ]
        },
    )
    assert r.status_code == 422


def test_a_member_who_is_not_the_author_cannot_reorder(ctx, db_session):
    client, login, event = ctx
    p1 = _photo_row(db_session, event.id, 1)
    db_session.commit()

    login("other-pw")
    r = client.put(
        "/api/events/1/media/order",
        json={"items": [{"type": "photo", "id": p1.id}]},
    )
    assert r.status_code == 403
