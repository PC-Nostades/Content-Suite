import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import UserRole
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

#: `create_type=False` porque los tipos ENUM los crea la migración 0001.
#: `values_callable` fuerza a SQLAlchemy a usar el *valor* del enum y no su nombre.
user_role_enum = PGEnum(
    UserRole,
    name="user_role",
    create_type=False,
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(
        user_role_enum, nullable=False, default=UserRole.creator
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"<User {self.email} role={self.role.value}>"


__all__ = ["User", "user_role_enum", "uuid"]
