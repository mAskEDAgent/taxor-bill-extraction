# scripts/eval_one.py
import json
import pandas as pd

# Load ground truth
gt_df = pd.read_csv("data/ground_truth/ground_truth.csv")

# Load one model result
with open("results/raw/gemini_bill_01.json") as f:
    result = json.load(f)

print("--- MODEL RESULT ---")
print(json.dumps(result, indent=2))

# Find matching ground truth row
bill_id = result["bill_id"]
gt_row = gt_df[gt_df["bill_id"] == bill_id].iloc[0]

print("\n--- GROUND TRUTH ROW ---")
print(gt_row)

print("\n--- SIDE BY SIDE ---")
if result["parse_success"]:
    parsed = result["parsed"]
    for field in ["vendor", "bill_number", "date", "amount", "currency", "gst_details"]:
        model_val = parsed.get(field)
        gt_val = gt_row[field]
        print(f"{field:15} | model: {str(model_val):35} | ground truth: {gt_val}")
else:
    print("This result failed to parse:", result["error"])