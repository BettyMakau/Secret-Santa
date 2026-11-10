"""Database models: a Group (one exchange) has many Members."""
import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def new_token() -> str:
    return secrets.token_urlsafe(16)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    budget = db.Column(db.String(50))
    exchange_date = db.Column(db.Date)
    # Organizer's private link — whoever has it can manage the group
    admin_token = db.Column(db.String(64), unique=True, nullable=False, default=new_token)
    drawn_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    members = db.relationship(
        "Member",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Member.id",
        foreign_keys="Member.group_id",
    )

    @property
    def is_drawn(self) -> bool:
        return self.drawn_at is not None


class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20), nullable=False)  # stored as digits, e.g. 254712345678
    wishlist = db.Column(db.Text, default="", nullable=False)
    # Member's private link — shows only who THEY are gifting
    access_token = db.Column(db.String(64), unique=True, nullable=False, default=new_token)
    recipient_id = db.Column(db.Integer, db.ForeignKey("member.id"))
    notified_at = db.Column(db.DateTime(timezone=True))

    group = db.relationship("Group", back_populates="members", foreign_keys=[group_id])
    recipient = db.relationship(
        "Member", remote_side=[id], foreign_keys=[recipient_id], post_update=True
    )
