# Handwritten Bill Extraction — Multi-Model Evaluation

A pipeline that extracts structured data from photos of handwritten bills using
three free-tier multimodal LLMs (Gemini, Mistral, Groq), evaluates their
accuracy field-by-field against a hand-verified ground truth, estimates
per-model cost, and pushes extracted data into Zoho Books as real expense
entries.

## Approach

1. Collected 13 real handwritten bills (kirana stores, restaurants, a tent
   house rental, an oil corporation receipt, etc.) — deliberately varied in
   handwriting style, paper condition, and format. Personal identifiers
   (phone numbers, individual names where present) were redacted before use.
2. Manually built a ground truth CSV with 6 fields per bill: vendor,
   bill_number, date, amount, currency, gst_details.
3. Sent each bill image to three vision-capable models — **Gemini 3.6 Flash**,
   **Mistral Pixtral 12B**, and **Groq's hosted Qwen 3.6 27B** — with an
   identical extraction prompt, requesting structured JSON output.
4. Scored every (model, bill, field) combination against ground truth using
   field-appropriate comparison logic (see Methodology).
5. Estimated per-model cost using real token usage where available and
   documented pricing.
6. Pushed a sample of extracted bills into Zoho Books via its Expenses API,
   demonstrating the pipeline works end-to-end, not just in isolation.

All three models were chosen specifically because they have genuine
no-credit-card free tiers, since this was built with zero budget.

## Repo structure

```
data/
  images/            13 bill photos (redacted)
  ground_truth/       hand-verified answer key (CSV)
scripts/
  extract_all.py      sends every bill to every model, saves raw + parsed JSON
  eval_all.py          scores every result against ground truth
  calculate_cost.py    computes per-model token cost
  push_to_zoho.py       pushes extracted bills into Zoho Books as expenses
results/
  raw/                 one JSON file per (model, bill) — full audit trail
  scores_detailed.csv   every field-level score
  accuracy_summary.csv  accuracy % by model × field
  cost_detailed.csv     per-call token cost
  cost_summary.csv      cost summary by model
notes.md               running development log (raw notes, kept for transparency)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate       # or venv/Scripts/activate on Windows
pip install -r requirements.txt
cp .env.example .env           # fill in your own API keys
python scripts/extract_all.py
python scripts/eval_all.py
python scripts/calculate_cost.py
python scripts/push_to_zoho.py
```

## Results

### Accuracy (% correct per field, 13 bills)

| Field       | Gemini    | Groq | Mistral   |
| ----------- | --------- | ---- | --------- |
| vendor      | 76.9      | 84.6 | 84.6      |
| bill_number | 76.9      | 76.9 | 61.5      |
| date        | 84.6      | 53.8 | 38.5      |
| amount      | **100.0** | 92.3 | 69.2      |
| currency    | 92.3      | 92.3 | **100.0** |
| gst_details | 84.6      | 84.6 | 76.9      |
| **Overall** | **85.9**  | 80.8 | 71.8      |

**No single model wins every field** — Groq and Mistral actually tie ahead of
Gemini on vendor name (84.6% vs 76.9%). But Gemini leads overall and, more
importantly, hits a perfect 100% on **amount** — the field with the highest
real-world stakes for bookkeeping accuracy.

**Date is the weakest field for every model** (38.5–84.6%), consistent with
handwritten digit sequences being genuinely harder to read reliably than
words. One bill in particular (`bill_01`) was read with a different date by
more than one model across separate runs, illustrating how ambiguous the
source handwriting can be even to a careful reader.

### Cost (per bill, extrapolated to 100 bills)

| Model   | Avg cost/bill | Per 100 bills |
| ------- | ------------- | ------------- |
| Mistral | $0.000073     | $0.0073       |
| Gemini  | $0.000442\*   | $0.0442\*     |
| Groq    | $0.002726     | $0.2726       |

\*Gemini's cost is only backed by real usage data on 1 of 13 calls (the
usage-logging fix was added partway through the project); the other 12 are
estimated from output length only and don't include image-input cost. Treat
Gemini's number as a likely-conservative floor, not a confirmed final figure.
Mistral's and Groq's numbers are fully backed by real per-call token data.

**Groq is clearly the most expensive per bill**, despite being the
"fastest/free" option — its output pricing is roughly 5x its input pricing,
and the model's visible chain-of-thought reasoning (see Methodology and
Limitations) burns real output tokens before it produces a final answer.

## Methodology — how "correct" was defined

Rather than one blended accuracy score, every field was scored independently
using field-appropriate logic, because a single average hides real
differences (e.g. Groq beats Gemini on vendor name even though Gemini wins
overall — a blended score would obscure that).

- **Vendor name** — fuzzy string match (threshold 0.75 similarity). Vendor
  names have harmless variation (case, minor spelling slips) that shouldn't
  be penalized as "wrong."
- **Bill number / amount** — numeric comparison after stripping commas and
  currency symbols, then casting to float. This avoids false negatives like
  `"004"` (model output, string) vs `4.0` (ground truth, float) — same real
  value, different representation.
- **Date** — exact match only, after normalizing both sides to `YYYY-MM-DD`.
  No fuzziness here deliberately: a wrong date is a wrong date for accounting
  purposes, "close" isn't good enough.
- **Currency** — normalized exact match (`Rs`, `Rs.`, `₹`, `rupees` all map
  to `INR`) before comparing, since models phrase the same currency
  differently without being factually wrong.
- **GST details** — this field needed a genuinely different approach.
  Generic fuzzy string matching initially scored verbose-but-correct answers
  (e.g. one model including full GSTIN numbers) as "wrong" against a much
  shorter ground truth string, purely due to length, not inaccuracy. Fixed
  by extracting just the meaningful signal — whether GST is mentioned at
  all, and which percentage rate(s) — and comparing that instead of the raw
  text.
- **Blank ground truth + blank model output = correct.** If a bill genuinely
  doesn't show a field (e.g. no bill number was written) and a model
  correctly returned null rather than inventing a value, that counts as a
  correct answer, not a skipped one.
- **Parse failures count as wrong on every field**, not excluded from the
  dataset. A model that can't return valid JSON at all is a real failure
  mode for this use case, and hiding it would make the accuracy numbers look
  better than reality.

## Limitations and honest gaps

- **Small sample.** 13 bills is enough to see real patterns (e.g. date being
  consistently hard) but not enough for statistically confident percentages.
  A production evaluation would want a much larger, more diverse set.
- **Gemini's cost figure is incomplete**, as noted above — only 1 of 13 calls
  has real token-usage data; the rest are output-only estimates missing
  image-input cost.
- **Groq's vision model is a preview-tier model** (`qwen/qwen3.6-27b`), not
  a stable production offering. Mid-project, Groq deprecated the model we
  started with entirely and we had to switch — worth knowing before relying
  on Groq's multimodal lineup for anything long-term.
- **Groq has a distinct failure mode the other two don't show**: on one
  bill with genuinely messy handwritten arithmetic, its visible
  chain-of-thought reasoning got stuck re-guessing the amount and never
  converged to a final answer, cutting off mid-thought rather than returning
  a (possibly wrong) value. This is arguably safer than silently returning
  a wrong answer, but only if a production pipeline is built to detect and
  handle "no answer" — this pipeline currently just counts it as wrong,
  same as any other failure.
- **The 0.75 vendor-name fuzzy-match threshold is a judgment call**, tuned by
  eyeballing real examples rather than a rigorous sweep — a reasonable
  starting point, not a scientifically optimized value.
- **Zoho integration covers 4 of 13 bills**, all from Gemini's extractions
  only, using a single generic expense category ("Other Expenses") rather
  than per-bill category inference. This demonstrates the pipeline works
  end-to-end; a production version would likely want the model to also
  suggest a category per bill, and push the full dataset.
- **Two real Zoho API quirks** were hit and fixed during integration:
  Zoho rejects an expense whose "paid through" account is the same as its
  expense category account, and the documented `filter_by=AccountType.Cash`
  query parameter didn't match Zoho's actual internal `cash` type string —
  worth knowing if extending this integration further.

## Recommendation

For a production handwritten-bill extraction pipeline, **Gemini 3.6 Flash is
the strongest default** — it leads on overall accuracy and specifically on
amount, the highest-stakes field for bookkeeping correctness, at a cost that
(even accounting for the estimation caveat above) is very unlikely to exceed
Groq's confirmed real cost. Groq's edge on vendor-name accuracy doesn't
offset being several times more expensive per bill and having a real
"fails to answer" behavior on hard cases. Mistral is by far the cheapest
option, but its accuracy trade-off — particularly on date (38.5%) and amount
(69.2%) — is significant enough that it's hard to recommend unless cost is
the dominant constraint over correctness.

A reasonable middle path for a real product: use Gemini as the primary
extractor, and flag bills where confidence seems low (e.g. very short or
malformed responses) for manual review, rather than trusting any single
model's output blindly at 85% accuracy.
