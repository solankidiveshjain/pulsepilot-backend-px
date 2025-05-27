"""
Database utility helper functions
"""
from typing import Any, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import SQLModel

async def upsert(
    session: AsyncSession,
    model: Type[SQLModel],
    values: dict,
    pk_field: str
) -> None:
    """
    Perform an upsert (INSERT ... ON CONFLICT DO UPDATE) for a SQLModel model.

    Args:
        session: AsyncSession instance
        model: SQLModel class representing the target table
        values: dict of column names to values for insert/update
        pk_field: name of the primary key field to detect conflicts on
    """
    stmt = pg_insert(model).values(**values)
    # Prepare update dict without primary key
    update_values = {k: v for k, v in values.items() if k != pk_field}
    stmt = stmt.on_conflict_do_update(
        index_elements=[pk_field],
        set_=update_values
    )
    await session.execute(stmt)
    await session.commit() 