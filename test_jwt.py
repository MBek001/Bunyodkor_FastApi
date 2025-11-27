#!/usr/bin/env python3
"""
Test JWT token creation and validation
"""
import asyncio
from app.core.security import create_access_token, decode_access_token
from app.core.config import settings

print("=" * 70)
print("JWT TOKEN TEST")
print("=" * 70)

# Test 1: Check config
print("\n1. Configuration:")
print(f"   SECRET_KEY: {settings.SECRET_KEY[:20]}...")
print(f"   ALGORITHM: {settings.ALGORITHM}")
print(f"   EXPIRE_MINUTES: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}")

# Test 2: Create a token
print("\n2. Creating test token...")
test_user_id = 1
token = create_access_token(data={"sub": test_user_id})
print(f"   Token created: {token[:50]}...")

# Test 3: Decode the token
print("\n3. Decoding token...")
payload = decode_access_token(token)

if payload is None:
    print("   ❌ FAILED: Token decode returned None")
    print("   This means JWT validation failed!")
else:
    print("   ✅ SUCCESS: Token decoded")
    print(f"   Payload: {payload}")

    # Test 4: Check sub field
    print("\n4. Checking 'sub' field...")
    if "sub" in payload:
        print(f"   ✅ 'sub' exists: {payload['sub']} (type: {type(payload['sub']).__name__})")
    else:
        print("   ❌ 'sub' field missing!")

# Test 5: Test with actual database
print("\n5. Testing with database...")
from app.core.db import AsyncSessionLocal
from app.models.auth import User
from sqlalchemy import select

async def test_db():
    async with AsyncSessionLocal() as db:
        # Check if user exists
        result = await db.execute(select(User).where(User.id == 1))
        user = result.scalar_one_or_none()

        if user:
            print(f"   ✅ User found: ID={user.id}, Phone={user.phone}, Status={user.status}")

            # Create token for this user
            user_token = create_access_token(data={"sub": user.id})
            print(f"\n6. Token for user {user.id}:")
            print(f"   Token: {user_token[:50]}...")

            # Decode it
            user_payload = decode_access_token(user_token)
            if user_payload:
                print(f"   ✅ Decoded successfully")
                print(f"   User ID from token: {user_payload.get('sub')}")
            else:
                print(f"   ❌ Failed to decode!")
        else:
            print("   ❌ No user with ID=1 found in database")
            print("   Run 'python seed.py' to create admin user")

asyncio.run(test_db())

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
