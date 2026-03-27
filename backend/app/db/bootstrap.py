import asyncio
import uuid
from typing import Any

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
from app.services.databricks_uc_service import DatabricksUnityCatalogService
from app.utils.datetime_utils import unix_to_minute_datetime
from sqlalchemy import delete, func, select
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
        if group.created_by != created_by:
            group.created_by = created_by
            await db.commit()
            await db.refresh(group)
        print(f"  Group already exists: {name}")
    return group


async def _ensure_member(db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id))
    if result.scalar_one_or_none() is None:
        db.add(GroupMember(group_id=group_id, user_id=user_id))
        await db.commit()
        print(f"  Added user {user_id} to group {group_id}")


async def _keep_only_group(db: AsyncSession, keep_group_id: uuid.UUID) -> None:
    count_stmt = select(func.count(Group.id)).where(Group.id != keep_group_id)
    groups_to_remove = await db.scalar(count_stmt)
    stmt = delete(Group).where(Group.id != keep_group_id)
    await db.execute(stmt)
    await db.commit()
    if groups_to_remove:
        print(f"  Removed {groups_to_remove} non-bootstrap group(s)")


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


async def _seed_dataset(db: AsyncSession, table: dict[str, Any], owner_id: uuid.UUID) -> Dataset:
    dataset_name = table["dataset_name"]
    display_name = table["display_name"]
    full_name = table["full_name"]
    description = table.get("description")
    if description is None:
        description = table.get("comment")
    metadata_json = {
        "id": dataset_name,
        "display_name": display_name,
        "description": description,
        "owner": table.get("owner"),
        "agency": "AGC",
        "update_frequency": "Daily",
        "data_quality": "Internal",
        "data_classification": "Confidential (Cloud-Eligible)",
        "updated_by": table.get("updated_by"),
        "updated_at": unix_to_minute_datetime(table.get("updated_at")),
        "formats": ["csv"],
        "source": "databricks_unity_catalog",
        "unity_catalog": {
            "catalog_name": table.get("catalog_name"),
            "schema_name": table.get("schema_name"),
            "table_name": display_name,
            "full_name": full_name,
            "table_type": table.get("table_type"),
        },
        "schema": table.get("columns", []),
    }
    result = await db.execute(select(Dataset).where(Dataset.dataset_name == dataset_name))
    dataset = result.scalar_one_or_none()
    if dataset is None:
        dataset = Dataset(
            dataset_name=dataset_name,
            display_name=display_name,
            description=description,
            owner_id=owner_id,
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)
        print(f"  Created dataset: {dataset_name}")
    else:
        dataset.description = description
        await db.commit()
        await db.refresh(dataset)
        print(f"  Dataset already exists, skipping create: {dataset_name}")

    result = await db.execute(select(DatasetMetadata).where(DatasetMetadata.dataset_id == dataset.id))
    dm = result.scalar_one_or_none()
    if dm is None:
        dm = DatasetMetadata(
            dataset_id=dataset.id,
            schema_name=table.get("schema_name"),
            table_name=dataset_name,
            source_system="databricks_unity_catalog",
            file_path=full_name,
            metadata_json=metadata_json,
        )
        db.add(dm)
    else:
        dm.schema_name = table.get("schema_name")
        dm.table_name = dataset_name
        dm.source_system = "databricks_unity_catalog"
        dm.file_path = full_name
        dm.metadata_json = metadata_json
    await db.commit()
    print(f"  Upserted metadata for dataset: {dataset_name}")
    return dataset


async def bootstrap_db() -> None:
    print("Creating database tables...")
    await create_tables()

    if not settings.DATABRICKS_UC_CATALOG or not settings.DATABRICKS_UC_SCHEMA:
        raise ValueError("DATABRICKS_UC_CATALOG and DATABRICKS_UC_SCHEMA must be configured")

    tables = await DatabricksUnityCatalogService().list_tables(
        catalog_name=settings.DATABRICKS_UC_CATALOG,
        schema_name=settings.DATABRICKS_UC_SCHEMA,
    )
    if not tables:
        print(f"No Unity Catalog tables found in " f"{settings.DATABRICKS_UC_CATALOG}.{settings.DATABRICKS_UC_SCHEMA}")

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
        user = await _upsert_user(
            db,
            email=settings.BOOTSTRAP_USER2_EMAIL,
            password=settings.BOOTSTRAP_USER2_PASSWORD,
            full_name="User",
            is_superuser=False,
        )

        # --- Datasets ---
        print(f"\nSeeding {len(tables)} dataset(s) from " f"{settings.DATABRICKS_UC_CATALOG}.{settings.DATABRICKS_UC_SCHEMA}...")
        datasets: dict[str, Dataset] = {}
        for table in tables:
            ds = await _seed_dataset(db, table, admin.id)
            datasets[ds.display_name] = ds

        # --- Group for analyst ---
        print("\nSeeding groups and permissions...")
        analyst_group = await _upsert_group(
            db,
            name="team-leaders",
            description="Officers that can only view officer case load datasets.",
            created_by=admin.id,
        )
        await _ensure_member(db, analyst_group.id, user.id)
        await _keep_only_group(db, analyst_group.id)

    print("\nBootstrap complete.")
    print(f"  Admin:   {settings.BOOTSTRAP_USER_EMAIL} / {settings.BOOTSTRAP_USER_PASSWORD}")
    print(f"  User:    {settings.BOOTSTRAP_USER2_EMAIL} / {settings.BOOTSTRAP_USER2_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(bootstrap_db())
