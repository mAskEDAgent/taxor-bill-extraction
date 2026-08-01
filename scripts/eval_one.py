# scripts/eval_one.py (updated)
import json
import pandas as pd
from rapidfuzz import fuzz

gt_df = pd.read_csv("data/ground_truth/ground_truth.csv")

with open("results/raw/gemini_bill_01.json") as f:
    result = json.load(f)

bill_id = result["bill_id"]
gt_row = gt_df[gt_df["bill_id"] == bill_id].iloc[0]

CURRENCY_MAP = {
    "rs": "INR", "rs.": "INR", "₹": "INR", "inr": "INR", "rupees": "INR",
}


def normalize_text(value):
    """Lowercase, strip whitespace. Handles None safely."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip().lower()


def normalize_number(value):
    """Strip commas/currency symbols, convert to float. Handles None safely."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    cleaned = str(value).replace(",", "").replace("₹", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_currency(value):
    norm = normalize_text(value)
    if norm is None:
        return None
    return CURRENCY_MAP.get(norm, norm.upper())

import re

def extract_gst_signal(text):
    """Pull out GST percentage(s) mentioned, and whether GST is present at all."""
    norm = normalize_text(text)
    if norm is None or norm == "":
        return {"present": False, "percentages": set()}
    if "none" in norm or "not mentioned" in norm or "no gst" in norm:
        return {"present": False, "percentages": set()}
    percentages = set(re.findall(r'(\d+(?:\.\d+)?)\s*%', norm))
    return {"present": True, "percentages": percentages}


def score_gst_details(model_val, gt_val):
    model_signal = extract_gst_signal(model_val)
    gt_signal = extract_gst_signal(gt_val)

    if model_signal["present"] != gt_signal["present"]:
        return False, "presence_mismatch"

    if not gt_signal["present"]:
        return True, "both_no_gst"

    # if ground truth doesn't specify a percentage, just presence matching is enough
    if not gt_signal["percentages"]:
        return True, "presence_match_no_pct_to_check"

    overlap = model_signal["percentages"] & gt_signal["percentages"]
    is_correct = len(overlap) > 0
    return is_correct, f"pct_match({overlap})" if is_correct else f"pct_mismatch(model={model_signal['percentages']}, gt={gt_signal['percentages']})"


def score_field(field, model_val, gt_val):
    """Returns (is_correct: bool, method: str) for one field."""

    # Both blank/null -> correct (model correctly recognized absence)
    gt_norm = normalize_text(gt_val)
    if gt_norm is None or gt_norm == "":
        model_norm = normalize_text(model_val)
        is_correct = (model_norm is None or model_norm == "" or model_norm == "none")
        return is_correct, "both_blank"

    if field == "vendor":
        model_norm = normalize_text(model_val) or ""
        similarity = fuzz.ratio(model_norm, gt_norm) / 100
        is_correct = similarity >= 0.75
        return is_correct, f"fuzzy({similarity:.2f})"

    elif field == "gst_details":
        return score_gst_details(model_val, gt_val)

    elif field == "date":
        model_norm = normalize_text(model_val)
        is_correct = (model_norm == gt_norm)
        return is_correct, "exact"

    elif field == "currency":
        is_correct = (normalize_currency(model_val) == normalize_currency(gt_val))
        return is_correct, "normalized_exact"

    elif field in ("amount", "bill_number"):
        model_num = normalize_number(model_val)
        gt_num = normalize_number(gt_val)
        is_correct = (model_num == gt_num)
        return is_correct, "numeric"

    return False, "unknown_field"


# Run scoring on this one result
print("--- SCORING ---")
if result["parse_success"]:
    parsed = result["parsed"]
    for field in ["vendor", "bill_number", "date", "amount", "currency", "gst_details"]:
        model_val = parsed.get(field)
        gt_val = gt_row[field]
        is_correct, method = score_field(field, model_val, gt_val)
        status = "CORRECT" if is_correct else "WRONG"
        print(f"{field:15} | {status:8} | method={method:20} | model={model_val!r:40} gt={gt_val!r}")
else:
    print("Parse failed, cannot score:", result["error"])