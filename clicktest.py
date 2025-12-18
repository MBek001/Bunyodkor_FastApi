import hashlib
import requests
from datetime import datetime


API_BASE_URL = "http://localhost:8000"
CLICK_ENDPOINT = f"{API_BASE_URL}/click/payment"

SERVICE_ID = 12345
SECRET_KEY = "your_secret_key_here"

TEST_CONTRACT_NUMBER = "CONTRACT-2024-001"
TEST_AMOUNT = 500000.0


def md5_hash(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def get_params_iv(params: dict) -> str:
    PARAMS_ORDER = ["contract", "full_name", "service_type", "amount", "payment_month", "payment_year"]
    return "".join(str(params[k]) for k in PARAMS_ORDER if k in params)


def generate_signature(click_paydoc_id, attempt_trans_id, service_id, params, action, sign_time):
    params_iv = get_params_iv(params)

    raw = (
        f"{click_paydoc_id}"
        f"{attempt_trans_id}"
        f"{service_id}"
        f"{SECRET_KEY}"
        f"{params_iv}"
        f"{action}"
        f"{sign_time}"
    )

    print(f"📝 Signature raw string: {raw}")
    signature = md5_hash(raw)
    print(f"🔐 Generated signature: {signature}")
    return signature


def test_action_0_getinfo():
    print("\n" + "="*60)
    print("🧪 TEST 1: Action 0 - GETINFO")
    print("="*60)

    payload = {
        "action": 0,
        "service_id": SERVICE_ID,
        "params": {
            "contract": TEST_CONTRACT_NUMBER
        }
    }

    print(f"📤 Request: {payload}")

    try:
        response = requests.post(CLICK_ENDPOINT, json=payload)
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("error") == 0:
                print("✅ SUCCESS: Contract found!")
                return data
            else:
                print(f"❌ ERROR {data.get('error')}: {data.get('error_note')}")
                return None
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return None


def test_action_1_prepare():
    print("\n" + "="*60)
    print("🧪 TEST 2: Action 1 - PREPARE")
    print("="*60)

    click_paydoc_id = 123456789
    attempt_trans_id = 987654321
    sign_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    params = {
        "contract": TEST_CONTRACT_NUMBER,
        "amount": TEST_AMOUNT
    }

    action = 1
    signature = generate_signature(
        click_paydoc_id,
        attempt_trans_id,
        SERVICE_ID,
        params,
        action,
        sign_time
    )

    payload = {
        "action": action,
        "click_paydoc_id": click_paydoc_id,
        "attempt_trans_id": attempt_trans_id,
        "service_id": SERVICE_ID,
        "sign_time": sign_time,
        "sign_string": signature,
        "params": params
    }

    print(f"📤 Request: {payload}")

    try:
        response = requests.post(CLICK_ENDPOINT, json=payload)
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("error") == 0:
                print("✅ SUCCESS: Transaction prepared!")
                print(f"💾 merchant_prepare_id: {data.get('merchant_prepare_id')}")
                return data
            else:
                print(f"❌ ERROR {data.get('error')}: {data.get('error_note')}")
                return None
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return None


def test_action_2_confirm(prepare_data):
    if not prepare_data:
        print("\n⚠️ SKIPPING TEST 3: No prepare data available")
        return None

    print("\n" + "="*60)
    print("🧪 TEST 3: Action 2 - CONFIRM")
    print("="*60)

    click_paydoc_id = prepare_data.get("click_paydoc_id")
    attempt_trans_id = prepare_data.get("attempt_trans_id")
    merchant_prepare_id = prepare_data.get("merchant_prepare_id")

    sign_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    params = {}

    action = 2
    signature = generate_signature(
        click_paydoc_id,
        attempt_trans_id,
        SERVICE_ID,
        params,
        action,
        sign_time
    )

    payload = {
        "action": action,
        "click_paydoc_id": click_paydoc_id,
        "attempt_trans_id": attempt_trans_id,
        "service_id": SERVICE_ID,
        "merchant_prepare_id": merchant_prepare_id,
        "sign_time": sign_time,
        "sign_string": signature,
        "params": params
    }

    print(f"📤 Request: {payload}")

    try:
        response = requests.post(CLICK_ENDPOINT, json=payload)
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("error") == 0:
                print("✅ SUCCESS: Transaction confirmed!")
                print(f"💾 merchant_confirm_id: {data.get('merchant_confirm_id')}")
                return data
            elif data.get("error") == -4:
                print("⚠️ Already confirmed or duplicate payment")
                return data
            else:
                print(f"❌ ERROR {data.get('error')}: {data.get('error_note')}")
                return None
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return None


def test_action_3_check(prepare_data):
    if not prepare_data:
        print("\n⚠️ SKIPPING TEST 4: No prepare data available")
        return None

    print("\n" + "="*60)
    print("🧪 TEST 4: Action 3 - CHECK")
    print("="*60)

    click_paydoc_id = prepare_data.get("click_paydoc_id")
    attempt_trans_id = prepare_data.get("attempt_trans_id")
    merchant_prepare_id = prepare_data.get("merchant_prepare_id")

    sign_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {}

    action = 3
    signature = generate_signature(
        click_paydoc_id,
        attempt_trans_id,
        SERVICE_ID,
        params,
        action,
        sign_time
    )

    payload = {
        "action": action,
        "click_paydoc_id": click_paydoc_id,
        "attempt_trans_id": attempt_trans_id,
        "service_id": SERVICE_ID,
        "merchant_prepare_id": merchant_prepare_id,
        "sign_time": sign_time,
        "sign_string": signature,
        "params": params
    }

    print(f"📤 Request: {payload}")

    try:
        response = requests.post(CLICK_ENDPOINT, json=payload)
        print(f"📥 Response status: {response.status_code}")
        print(f"📥 Response: {response.json()}")

        if response.status_code == 200:
            data = response.json()
            if data.get("error") == 0:
                status = data.get("status")
                status_map = {
                    0: "PENDING (Click will retry)",
                    1: "FAILED (Click will cancel)",
                    2: "SUCCESS (Click will mark as paid)"
                }
                print(f"✅ SUCCESS: Status = {status} ({status_map.get(status, 'Unknown')})")
                return data
            else:
                print(f"❌ ERROR {data.get('error')}: {data.get('error_note')}")
                return None
        else:
            print(f"❌ HTTP ERROR: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return None


def main():
    print("\n" + "="*60)
    print("🚀 CLICK PAYMENT INTEGRATION TEST SUITE")
    print("="*60)
    print(f"📍 Endpoint: {CLICK_ENDPOINT}")
    print(f"🔑 Service ID: {SERVICE_ID}")
    print(f"📄 Test Contract: {TEST_CONTRACT_NUMBER}")
    print(f"💰 Test Amount: {TEST_AMOUNT}")
    print("="*60)

    getinfo_result = test_action_0_getinfo()
    prepare_result = test_action_1_prepare()
    confirm_result = test_action_2_confirm(prepare_result)
    check_result = test_action_3_check(prepare_result)

    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Test 1 (Getinfo):  {'✅ PASSED' if getinfo_result else '❌ FAILED'}")
    print(f"Test 2 (Prepare):  {'✅ PASSED' if prepare_result else '❌ FAILED'}")
    print(f"Test 3 (Confirm):  {'✅ PASSED' if confirm_result else '⏭️ SKIPPED' if not prepare_result else '❌ FAILED'}")
    print(f"Test 4 (Check):    {'✅ PASSED' if check_result else '⏭️ SKIPPED' if not prepare_result else '❌ FAILED'}")
    print("="*60)

    print("\n💡 NOTES:")
    print("- If all tests pass, your Click integration is working correctly!")
    print("- If Getinfo fails, check if the contract exists and is ACTIVE")
    print("- If Prepare fails with -1, check signature calculation and SECRET_KEY")
    print("- If Prepare fails with -4, the month is already paid")
    print("- If Prepare fails with -5, contract may be outside valid period")
    print("- If Confirm fails with -4, the payment is already confirmed or duplicate")
    print("\n")


if __name__ == "__main__":
    print("\n⚠️ IMPORTANT: Before running this script:")
    print("1. Update SERVICE_ID and SECRET_KEY in this file")
    print("2. Update TEST_CONTRACT_NUMBER with a real contract from your DB")
    print("3. Make sure FastAPI server is running on http://localhost:8000")
    print("4. Make sure the contract is ACTIVE and within valid date range")
    input("\n✅ Press ENTER to continue...")

    main()
