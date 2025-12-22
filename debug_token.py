#!/usr/bin/env python3
"""
Debug script to test JWT token validation
"""
import sys
from jose import jwt
from app.core.config import settings

if len(sys.argv) < 2:
    print("Usage: python debug_token.py <your-token>")
    sys.exit(1)

token = sys.argv[1]

print("=" * 60)
print("JWT TOKEN DEBUG")
print("=" * 60)

try:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    print("✅ Token is valid!")
    print("\nPayload contents:")
    for key, value in payload.items():
        print(f"  {key}: {value} (type: {type(value).__name__})")

    if "sub" in payload:
        print(f"\n✅ 'sub' field exists: {payload['sub']}")
        print(f"   Type: {type(payload['sub']).__name__}")
    else:
        print("\n❌ 'sub' field is missing from payload!")

except jwt.ExpiredSignatureError:
    print("❌ Token has expired")
except jwt.JWTError as e:
    print(f"❌ Invalid token: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

print("=" * 60)
