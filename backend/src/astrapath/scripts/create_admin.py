import argparse
import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from astrapath.audit import AuditService, system_audit_context
from astrapath.db import SessionLocal
from astrapath.enums import Role, UserStatus
from astrapath.models import User
from astrapath.security import hash_password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an AstraPath admin account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--oidc-issuer")
    parser.add_argument("--oidc-subject")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if bool(args.oidc_issuer) != bool(args.oidc_subject):
        raise SystemExit("--oidc-issuer and --oidc-subject must be provided together")
    password_hash = None
    if not args.oidc_subject:
        password = getpass.getpass("Admin password (minimum 12 characters): ")
        if len(password) < 12:
            raise SystemExit("Password must contain at least 12 characters")
        password_hash = hash_password(password)

    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email.strip().lower()))
    except ValidationError as exc:
        raise SystemExit("Admin email must be a valid email address") from exc
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("A user with that email already exists")
        admin = User(
            email=email,
            full_name=args.name.strip(),
            role=Role.ADMIN,
            status=UserStatus.ACTIVE,
            password_hash=password_hash,
            oidc_issuer=args.oidc_issuer,
            oidc_subject=args.oidc_subject,
        )
        db.add(admin)
        db.flush()
        AuditService().record(
            db,
            system_audit_context({"bootstrap": True}),
            action="admin.account_bootstrapped",
            resource_type="user",
            resource_id=admin.id,
            after={"email": admin.email, "role": admin.role.value},
        )
        db.commit()
    print(f"Created admin {email}")


if __name__ == "__main__":
    main()
