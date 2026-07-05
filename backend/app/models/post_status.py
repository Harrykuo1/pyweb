import enum


class PostStatus(str, enum.Enum):
    """Shared moderation status for member-submitted posts (jobs & events).

    Member submissions start PENDING and need admin ACCEPT to publish.
    Admin-authored/proxy posts are created ACCEPTED. REJECTED carries a
    reason and can be revised & resubmitted by the author.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
