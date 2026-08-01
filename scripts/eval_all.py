import json
import re
import glob
import os
import pandas as pd
from rapidfuzz import fuzz

gt_df = pd.read_csv("data/ground_truth/ground_truth.csv")

CURRENCY_MAP = {
    "rs": "INR", "rs.": "INR", "₹": "INR", "inr": "INR", "rupees": "INR",
}

FIELDS = ["vendor", "bill_number", "date", "amount", "currency", "gst_details"]


def normalize_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip().lower()


def normalize_number(value):
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


def extract_gst_signal(text):
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
    if not gt_signal["percentages"]:
        return True, "presence_match_no_pct_to_check"
    overlap = model_signal["percentages"] & gt_signal["percentages"]
    return len(overlap) > 0, "pct_match" if overlap else "pct_mismatch"


def score_field(field, model_val, gt_val):
    gt_norm = normalize_text(gt_val)
    if gt_norm is None or gt_norm == "":
        model_norm = normalize_text(model_val)
        is_correct = (model_norm is None or model_norm == "" or model_norm == "none")
        return is_correct, "both_blank"

    if field == "vendor":
        model_norm = normalize_text(model_val) or ""
        similarity = fuzz.ratio(model_norm, gt_norm) / 100
        return similarity >= 0.75, f"fuzzy({similarity:.2f})"
    elif field == "gst_details":
        return score_gst_details(model_val, gt_val)
    elif field == "date":
        return normalize_text(model_val) == gt_norm, "exact"
    elif field == "currency":
        return normalize_currency(model_val) == normalize_currency(gt_val), "normalized_exact"
    elif field in ("amount", "bill_number"):
        return normalize_number(model_val) == normalize_number(gt_val), "numeric"
    return False, "unknown_field"


# --- Run scoring across every result file ---
rows = []
result_files = sorted(glob.glob("results/raw/*.json"))
print(f"Found {len(result_files)} result files")

for filepath in result_files:
    with open(filepath) as f:
        result = json.load(f)

    bill_id = result["bill_id"]
    model = result["model"]

    gt_matches = gt_df[gt_df["bill_id"] == bill_id]
    if gt_matches.empty:
        print(f"WARNING: no ground truth for {bill_id}, skipping")
        continue
    gt_row = gt_matches.iloc[0]

    if not result["parse_success"]:
        for field in FIELDS:
            rows.append({
                "bill_id": bill_id, "model": model, "field": field,
                "correct": False, "method": "parse_failed"
            })
        continue

    parsed = result["parsed"]
    for field in FIELDS:
        model_val = parsed.get(field)
        gt_val = gt_row[field]
        is_correct, method = score_field(field, model_val, gt_val)
        rows.append({
            "bill_id": bill_id, "model": model, "field": field,
            "correct": is_correct, "method": method
        })

scores_df = pd.DataFrame(rows)
os.makedirs("results", exist_ok=True)
scores_df.to_csv("results/scores_detailed.csv", index=False)
print(f"\nSaved detailed scores to results/scores_detailed.csv ({len(scores_df)} rows)")

# --- Build the summary table: accuracy % per model per field ---
summary = scores_df.groupby(["model", "field"])["correct"].mean().unstack() * 100
summary = summary.round(1)
summary = summary[FIELDS]  # keep consistent column order

print("\n--- ACCURACY BY MODEL AND FIELD (%) ---")
print(summary)

summary.to_csv("results/accuracy_summary.csv")
print("\nSaved summary to results/accuracy_summary.csv")

# --- Overall accuracy per model (average across fields) ---
overall = scores_df.groupby("model")["correct"].mean() * 100
print("\n--- OVERALL ACCURACY PER MODEL (%) ---")
print(overall.round(1))