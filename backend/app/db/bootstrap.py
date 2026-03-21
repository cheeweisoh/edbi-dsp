import asyncio
import json
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.security import hash_password
from app.db.init_db import create_tables
from app.db.session import AsyncSessionLocal
from app.models.dataset import Dataset
from app.models.dataset_metadata import DatasetMetadata
from app.models.dataset_permission import DatasetPermission
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _upsert_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    is_superuser: bool,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_superuser=is_superuser,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"  Created user: {email} (superuser={is_superuser})")
    else:
        # Ensure is_superuser flag is correct in case it changed
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            await db.commit()
            await db.refresh(user)
        print(f"  User already exists: {email}")
    return user


async def _upsert_group(
    db: AsyncSession,
    name: str,
    description: str | None,
    created_by: uuid.UUID,
) -> Group:
    result = await db.execute(select(Group).where(Group.name == name))
    group = result.scalar_one_or_none()
    if group is None:
        group = Group(name=name, description=description, created_by=created_by)
        db.add(group)
        await db.commit()
        await db.refresh(group)
        print(f"  Created group: {name}")
    else:
        print(f"  Group already exists: {name}")
    return group


async def _ensure_member(db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id))
    if result.scalar_one_or_none() is None:
        db.add(GroupMember(group_id=group_id, user_id=user_id))
        await db.commit()
        print(f"  Added user {user_id} to group {group_id}")


async def _ensure_permission(
    db: AsyncSession,
    dataset_id: uuid.UUID,
    grantee_type: str,
    grantee_id: uuid.UUID,
    permission: str,
    granted_by: uuid.UUID,
) -> None:
    result = await db.execute(
        select(DatasetPermission).where(
            DatasetPermission.dataset_id == dataset_id,
            DatasetPermission.grantee_type == grantee_type,
            DatasetPermission.grantee_id == grantee_id,
        )
    )
    perm = result.scalar_one_or_none()
    if perm is None:
        db.add(
            DatasetPermission(
                dataset_id=dataset_id,
                grantee_type=grantee_type,
                grantee_id=grantee_id,
                permission=permission,
                granted_by=granted_by,
            )
        )
        await db.commit()
        print(f"  Granted '{permission}' on dataset {dataset_id} to {grantee_type} {grantee_id}")
    else:
        print(f"  Permission already exists for {grantee_type} {grantee_id} on dataset {dataset_id}")


async def _seed_dataset(db: AsyncSession, meta: dict, owner_id: uuid.UUID) -> Dataset:
    name = meta["id"]
    result = await db.execute(select(Dataset).where(Dataset.name == name))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        dataset = Dataset(
            name=name,
            description=meta.get("description"),
            owner_id=owner_id,
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)
        print(f"  Created dataset: {name}")
    else:
        print(f"  Dataset already exists, skipping create: {name}")

    result = await db.execute(select(DatasetMetadata).where(DatasetMetadata.dataset_id == dataset.id))
    dm = result.scalar_one_or_none()
    if dm is None:
        dm = DatasetMetadata(
            dataset_id=dataset.id,
            schema_name=meta.get("schema_name"),
            table_name=meta.get("table_name"),
            source_system=meta.get("source"),
            file_path=meta.get("path"),
            metadata_json=meta,
        )
        db.add(dm)
    else:
        dm.schema_name = meta.get("schema_name")
        dm.table_name = meta.get("table_name")
        dm.source_system = meta.get("source")
        dm.file_path = meta.get("path")
        dm.metadata_json = meta
    await db.commit()
    print(f"  Upserted metadata for dataset: {name}")
    return dataset


async def bootstrap_db() -> None:
    print("Creating database tables...")
    await create_tables()

    data_dir = Path(settings.DATA_DIR)
    metadata_files = sorted(data_dir.glob("*_metadata.json"))
    if not metadata_files:
        print(f"No metadata files found in {data_dir.resolve()}")
        return

    async with AsyncSessionLocal() as db:
        # --- Users ---
        print("\nSeeding users...")
        admin = await _upsert_user(
            db,
            email=settings.BOOTSTRAP_USER_EMAIL,
            password=settings.BOOTSTRAP_USER_PASSWORD,
            full_name="System Admin",
            is_superuser=True,
        )
        analyst = await _upsert_user(
            db,
            email=settings.BOOTSTRAP_USER2_EMAIL,
            password=settings.BOOTSTRAP_USER2_PASSWORD,
            full_name="Data Analyst",
            is_superuser=False,
        )

        # --- Datasets ---
        print(f"\nSeeding {len(metadata_files)} dataset(s) from {data_dir.resolve()}...")
        datasets: dict[str, Dataset] = {}
        for meta_file in metadata_files:
            with meta_file.open() as f:
                meta = json.load(f)
            ds = await _seed_dataset(db, meta, admin.id)
            datasets[ds.name] = ds

        # --- Group for analyst ---
        print("\nSeeding groups and permissions...")
        analyst_group = await _upsert_group(
            db,
            name="electricity-viewers",
            description="Users who can view and query the electricity sales dataset",
            created_by=admin.id,
        )
        await _ensure_member(db, analyst_group.id, analyst.id)

        # Grant query access on electricity_sales only
        if "electricity_sales" in datasets:
            await _ensure_permission(
                db,
                dataset_id=datasets["electricity_sales"].id,
                grantee_type="group",
                grantee_id=analyst_group.id,
                permission="query",
                granted_by=admin.id,
            )

    print("\nBootstrap complete.")
    print(f"  Admin:   {settings.BOOTSTRAP_USER_EMAIL} / {settings.BOOTSTRAP_USER_PASSWORD}")
    print(f"  Analyst: {settings.BOOTSTRAP_USER2_EMAIL} / {settings.BOOTSTRAP_USER2_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(bootstrap_db())
