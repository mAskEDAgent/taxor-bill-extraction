import json
import glob
import pandas as pd

# Pricing per 1 million tokens (checked against official docs, Aug 2026)
PRICING = {
    "gemini":  {"input": 1.50, "output": 7.50},
    "mistral": {"input": 0.15, "output": 0.15},
    "groq":    {"input": 0.60, "output": 3.00},
}


def estimate_tokens_from_text(text):
    """Rough fallback: ~4 characters per token for English text."""
    if not text:
        return 0
    return len(text) / 4


rows = []
result_files = sorted(glob.glob("results/raw/*.json"))

for filepath in result_files:
    with open(filepath) as f:
        result = json.load(f)

    model = result["model"]
    bill_id = result["bill_id"]

    if result.get("usage"):
        # Real token counts, captured directly from the API response
        input_tokens = result["usage"]["input_tokens"]
        output_tokens = result["usage"]["output_tokens"]
        source = "real"
    else:
        # Estimate: only the output text length is known;
        # input (image + prompt) can't be reconstructed after the fact,
        # so we only estimate output cost for these older files.
        output_tokens = estimate_tokens_from_text(result.get("raw_response", ""))
        input_tokens = None
        source = "estimated_output_only"

    input_cost = (input_tokens / 1_000_000 * PRICING[model]["input"]) if input_tokens is not None else None
    output_cost = (output_tokens / 1_000_000 * PRICING[model]["output"])
    total_cost = (input_cost + output_cost) if input_cost is not None else output_cost

    rows.append({
        "bill_id": bill_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": round(output_tokens, 1),
        "input_cost_usd": round(input_cost, 6) if input_cost is not None else None,
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
        "source": source,
    })

cost_df = pd.DataFrame(rows)
cost_df.to_csv("results/cost_detailed.csv", index=False)
print(f"Saved detailed costs to results/cost_detailed.csv ({len(cost_df)} rows)")

print("\n--- COST SUMMARY BY MODEL ---")
summary = cost_df.groupby("model").agg(
    total_cost_usd=("total_cost_usd", "sum"),
    avg_cost_per_bill_usd=("total_cost_usd", "mean"),
    files_with_real_usage=("source", lambda x: (x == "real").sum()),
    files_estimated=("source", lambda x: (x == "estimated_output_only").sum()),
).round(6)
print(summary)

summary.to_csv("results/cost_summary.csv")
print("\nSaved summary to results/cost_summary.csv")

print("\n--- EXTRAPOLATED TO 100 BILLS (rough, based on today's per-bill average) ---")
extrapolated = (summary["avg_cost_per_bill_usd"] * 100).round(4)
print(extrapolated)