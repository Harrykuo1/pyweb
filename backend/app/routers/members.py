from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models import Member
from app.schemas import MemberCreate, MemberResponse, MemberUpdate

router = APIRouter(prefix="/api/members", tags=["members"])


@router.get("", response_model=list[MemberResponse])
def list_members(
    order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> list[Member]:
    column = Member.joined_at.asc() if order == "asc" else Member.joined_at.desc()
    return db.query(Member).order_by(column).all()


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(get_current_user),
) -> Member:
    member = db.query(Member).filter_by(id=member_id).one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Member:
    member = Member(
        graduation_year=payload.graduation_year,
        real_name=payload.real_name,
        current_position=payload.current_position,
        resume_md=payload.resume_md,
        joined_at=payload.joined_at or datetime.now(timezone.utc),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> Member:
    member = db.query(Member).filter_by(id=member_id).one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)

    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_admin),
) -> None:
    member = db.query(Member).filter_by(id=member_id).one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    db.delete(member)
    db.commit()
