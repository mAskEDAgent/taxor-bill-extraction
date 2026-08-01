# scripts/push_to_zoho.py
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()


def get_access_token():
    resp = requests.post(
        "https://accounts.zoho.in/oauth/v2/token",
        params={
            "grant_type": "refresh_token",
            "client_id": os.getenv("ZOHO_CLIENT_ID"),
            "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
            "refresh_token": os.getenv("ZOHO_REFRESH_TOKEN"),
        }
    )
    return resp.json()["access_token"]


def create_expense(access_token, bill_id, vendor, date, amount):
    url = "https://www.zohoapis.in/books/v3/expenses"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    params = {"organization_id": os.getenv("ZOHO_ORGANIZATION_ID")}

    payload = {
        "account_id": os.getenv("ZOHO_EXPENSE_ACCOUNT_ID"),
        "date": date,
        "amount": amount,
        "paid_through_account_id": os.getenv("ZOHO_PAID_THROUGH_ACCOUNT_ID"),
        "vendor_name": vendor,
        "description": f"Auto-extracted from {bill_id} (Taxor screening task, Gemini extraction)",
        "reference_number": bill_id,
    }

    resp = requests.post(url, headers=headers, params=params, json=payload)
    return resp.json()


# Pick a handful of bills to push -- using Gemini's results, the most accurate model
BILLS_TO_PUSH = ["bill_01", "bill_04", "bill_09", "bill_10"]

access_token = get_access_token()

for bill_id in BILLS_TO_PUSH:
    filepath = f"results/raw/gemini_{bill_id}.json"
    with open(filepath) as f:
        result = json.load(f)

    if not result["parse_success"]:
        print(f"SKIP {bill_id}: extraction failed, nothing to push")
        continue

    parsed = result["parsed"]
    vendor = parsed.get("vendor") or "Unknown Vendor"
    date = parsed.get("date") or "2026-01-01"  # Zoho requires a date; fallback if missing
    amount = parsed.get("amount")

    if amount is None:
        print(f"SKIP {bill_id}: no amount extracted, cannot create expense")
        continue

    print(f"Pushing {bill_id}: {vendor}, {date}, ₹{amount}")
    result = create_expense(access_token, bill_id, vendor, date, amount)

    if result.get("code") == 0:
        print(f"  SUCCESS - expense_id: {result['expense']['expense_id']}")
    else:
        print(f"  FAILED: {result}")