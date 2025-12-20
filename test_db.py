"""
Test database connection and async setup
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text


async def test_connection():
    print("🔍 Testing database connection...")

    # Create engine
    engine = create_async_engine(
        "postgresql+asyncpg://user:password@localhost:5432/bunyodkor_db",
        echo=True
    )

    # Create session
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with async_session() as session:
            # Test simple query
            result = await session.execute(text("SELECT 1"))
            print(f"✅ Database connection successful: {result.scalar()}")

            # Test groups table
            result = await session.execute(text("SELECT COUNT(*) FROM groups"))
            count = result.scalar()
            print(f"✅ Groups table accessible: {count} groups found")

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()
        print("🔒 Connection closed")


if __name__ == "__main__":
    asyncio.run(test_connection())
