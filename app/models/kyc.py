from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.orm import relationship

from app.database import Base


class KYC(Base):
    __tablename__ = "kyc"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    pan_number = Column(
        String(10),
        unique=True,
        nullable=False
    )

    aadhaar_last4 = Column(
        String(4),
        nullable=False
    )

    full_name = Column(
        String(100),
        nullable=False
    )

    date_of_birth = Column(
        Date,
        nullable=False
    )

    status = Column(
        Enum("Pending", "Approved", "Rejected"),
        default="Pending",
        nullable=False
    )

    rejection_reason = Column(
        String(255),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    user = relationship("User")