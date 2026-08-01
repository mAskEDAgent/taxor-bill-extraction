# Project Notes — findings to use in final write-up

Running scratchpad. Add a bullet whenever something notable happens during
extraction/eval. Doesn't need to be polished — just enough detail to remember
what happened when writing the README later.

## Model/setup quirks

- **Groq's vision model (`qwen/qwen3.6-27b`) is a preview model**, not
  production-tier. Groq's multimodal lineup changes frequently — the model we
  started with (`meta-llama/llama-4-scout-17b-16e-instruct`) was deprecated
  mid-project and had to be swapped. Worth a line in the write-up about model
  availability being a real practical constraint when working with free/fast
  inference providers.

- **Groq returns a `<think>...</think>` reasoning block** before its actual
  JSON answer. Had to strip this out to parse the response. Downside for
  parsing, but upside for transparency — see below.

- **Mistral and Groq both wrap JSON output in ` ```json ... ``` ` markdown
  fences** despite the prompt explicitly saying not to. Gemini did not do
  this. Had to add fence-stripping to the parsing step for all three models
  to be handled consistently.

## Per-bill findings (bill_01 — Bharat Associates invoice)

- **Mistral misread this bill significantly**: extracted vendor as "Eastern
  Leased Photocopy (P) Ltd." / "Eastern Logistics Pvt Ltd" (inconsistent
  across runs) instead of the actual "Bharat Associates", and amount as
  ~6924 instead of the actual 32345. This looks like a genuine
  misread/hallucination, not a parsing issue — worth flagging as a real
  accuracy gap for Mistral on this bill type.

- **Gemini and Groq both correctly read** vendor (Bharat Associates), amount
  (32345), and GST structure on this bill. Minor disagreement on the exact
  date read from handwriting (varied across runs between 01-13, 01-15,
  11-15 — suggests the handwritten date is genuinely ambiguous/hard to
  read, good example bill for illustrating handwriting difficulty).

- **Groq's reasoning trace (before stripping) showed real self-correction**:
  it initially misread a number, then re-examined the image and corrected
  itself before giving the final answer. Interesting qualitative
  difference vs Gemini/Mistral which just return an answer with no visible
  reasoning. Could be worth keeping the raw (unstripped) Groq output
  alongside the parsed JSON in results/raw/, purely for this kind of
  qualitative comparison in the write-up.

## Data-format gotchas (need normalization before scoring)

- **Currency**: Groq returned `"Rs"` instead of `"INR"` (which Gemini/Mistral
  and ground truth use). Not wrong, just different phrasing. Needs a
  normalization map before comparing in the eval script (Phase 4), e.g.
  `{"rs": "INR", "rs.": "INR", "₹": "INR", "rupees": "INR"}` — otherwise
  the scoring script would falsely mark this as incorrect.

- **Amount**: watch for commas in numbers (e.g. "32,345" vs 32345) —
  strip before numeric comparison.

- **Dates**: ground truth is normalized to YYYY-MM-DD; models mostly
  comply when explicitly told to, but double check every result before
  scoring since handwritten dates are genuinely ambiguous source material.

- **gst_details**: originally Gemini returned this as a nested JSON object
  (sub-fields like cgst_rate, sgst_amount, gstin numbers) instead of a
  plain string, which didn't match the ground truth format. Fixed by making
  the prompt explicitly require a short plain-text string for this field.

## Eval methodology decisions (Phase 4 — for write-up "reasoning" section)

- **Field-by-field scoring, not one blended accuracy number.** A single
  average hides real differences — e.g. Groq beats Gemini on vendor and
  bill_number even though Gemini has the higher overall average. Reporting
  per-field lets someone pick the right model for the field they actually
  care about, rather than trusting one misleading top-line score.

- **Vendor name**: fuzzy string match (rapidfuzz `fuzz.ratio`), threshold
  0.75 = correct. Chose fuzzy over exact because vendor names have harmless
  variation (case, minor OCR-style slips) that shouldn't count as wrong.
  0.75 picked by eyeballing real examples rather than guessing — worth
  rechecking against a few more bills before finalizing this number in the
  write-up.

- **bill_number and amount**: numeric comparison after stripping commas/
  currency symbols and casting to float. This fixes false negatives like
  `"004"` (model, string) vs `4.0` (ground truth, float) — same value,
  different representation. Plain `==` would have wrongly failed this.

- **date**: exact match only, after normalizing both sides to lowercase
  strings in YYYY-MM-DD. No fuzziness here on purpose — a wrong date is a
  wrong date, this is a field where being "close" isn't good enough for
  real accounting use.

- **currency**: normalized exact match via a small mapping (`Rs`, `Rs.`,
  `₹`, `rupees` → `INR`) before comparing. See currency gotcha above.

- **gst_details**: switched from generic fuzzy string matching to a custom
  percentage-extraction check, because verbose-but-correct answers (e.g.
  including full GSTIN numbers) were scoring as "wrong" against a short
  ground truth string purely due to length/wording, not actual inaccuracy.
  Logic: (1) does presence/absence of GST agree between model and ground
  truth, (2) if GST is present and ground truth specifies a rate, does at
  least one matching percentage number appear anywhere in the model's
  answer. This is a good example of "generic fuzzy matching isn't always
  the right tool" — worth explicitly explaining this reasoning in the
  write-up methodology section.

- **Both blank = correct.** If ground truth has no value for a field (bill
  genuinely doesn't show it) and the model also returned null/empty, that
  counts as correct — the model correctly recognized the absence rather
  than hallucinating a value. Implemented as an early check in
  `score_field()` before any field-specific logic runs.

- **Parse failures counted as wrong on every field**, not excluded from
  the dataset. A model that can't even return valid JSON is a real failure
  mode for this use case and should drag its score down accordingly, not
  be quietly dropped from the average.

## First full run results (39 files, 2 pending retries — bill_08 groq, bill_13 gemini still failed at this point)

Overall accuracy: Gemini 78.2%, Groq 73.1%, Mistral 71.8%.

Per-field, nothing is uniformly best:

- Gemini leads on amount (92.3%) and currency (84.6%, tied with Groq).
- Groq leads on vendor (76.9%, tied with Mistral) and bill_number (76.9%).
- Mistral leads on currency alone (100%) but is worst on date (38.5%) and
  amount (69.2%).
- **Date is the weakest field for every model** (38.5–76.9%) — likely the
  genuinely hardest field since handwritten digit sequences (e.g. "11" vs
  "01") are more ambiguous than words. Good candidate for a specific
  example/callout in the write-up (bill_01's date was misread differently
  by more than one model).

Note: these numbers include 2 results that failed due to infra issues, not
model inaccuracy (Groq 503 overload on bill_08, Gemini daily quota
exhausted on bill_13) — both auto-scored as wrong on all 6 fields under
the "parse failures count as wrong" rule. Rerun eval after those two are
successfully retried, numbers will shift slightly. Don't quote this run's
exact numbers as final in the write-up — rerun and use the post-retry
version instead.

## Second run results (38/39 files — groq_bill_08 retry succeeded, gemini_bill_13 still blocked on daily quota)

Overall accuracy: Groq 80.8% (up from 73.1%), Gemini 78.2% (unchanged —
still missing bill_13), Mistral 71.8% (unchanged).

Groq's retry on bill_08 clearly wasn't a fluke previously — once it
actually got a response, it jumped ahead of Gemini on vendor (84.6 vs
69.2), bill_number (84.6 vs 69.2), amount (92.3, tied), and currency
(92.3 vs 84.6). Groq is currently leading overall.

**Important caveat — do not treat this as the final ranking.** Gemini's
number is still artificially low because gemini_bill_13 has not
successfully extracted yet (still hitting the free-tier daily quota cap —
20 requests/day) and is being auto-scored as wrong on all 6 fields under
the "parse failures count as wrong" rule. That's 12 of Gemini's 78
field-scores being zeroed out due to an infra limit, not a real misread.
Rerun eval_all.py once gemini_bill_13 finally succeeds (likely needs to
wait for the daily quota to reset — try again the next day) before
quoting a final "which model wins" conclusion in the write-up.

## Cost calculation (Phase 4, cost piece)

Pricing used (checked against official docs / provider pages, Aug 2026):

- Gemini 3.6 Flash: $1.50 / $7.50 per 1M input/output tokens
- Mistral Pixtral 12B: $0.15 / $0.15 per 1M input/output tokens
- Groq (Qwen 3.6 27B): $0.60 / $3.00 per 1M input/output tokens — output
  is notably expensive relative to input on Groq specifically (5x), worth
  flagging since it changes the cost picture for a reasoning model that
  produces long `<think>` blocks before answering.

**Important limitation to state explicitly in the write-up**: the first
38 extraction results were captured before token-usage logging was added
to the script, so their costs are estimated from output text length only
(~4 chars/token heuristic) — input cost (which includes the image, the
most expensive part of a vision call) could not be reconstructed after
the fact for those files. Re-ran Mistral and Groq afterward (no daily cap
risk, unlike Gemini) once usage-logging was added, so those two now have
real per-call token costs. Gemini's bill_13 retry also succeeded same-day
(quota reset sooner than the typical midnight-Pacific expectation) so it
has real usage data too — meaning by the end, most/all files should have
real usage. Don't report the early estimate-only cost numbers as final —
use the numbers from the last full clean run.

## Groq reasoning-loop failure mode (bill_03)

Groq's model (Qwen 3.6 27B, via `<think>` reasoning) got stuck in an
extended, unresolved internal monologue on bill_03 specifically — kept
re-guessing handwritten amounts (130? 180? 260?) without ever reaching a
final answer, so the response got cut off mid-thought with no closing
`</think>` tag and no JSON at all. Raised `max_completion_tokens` from
default to 4096, tried again — still failed on this specific bill (other
bills fixed fine at 4096). This looks like a genuine model behavior, not
a bug in the script: bill_03's amounts are legitimately messy/ambiguous
handwriting, and Gemini/Mistral both still managed to produce an answer
on it (right or wrong) while Groq's reasoning loop just never converged.

This is worth a specific callout in the write-up: unlike Gemini/Mistral
which always return _something_ (even if occasionally inaccurate), Groq's
reasoning model can fail to answer at all on sufficiently ambiguous input
— a real, distinct failure mode worth knowing about if choosing a model
for a production pipeline (an extraction that error-cleanly is arguably
safer than one that silently returns a plausible-looking wrong answer,
but only if the pipeline actually checks for and handles "no answer").

## Infra timing note

Gemini's free-tier daily quota reset same-day rather than requiring a
full wait until the next day (had assumed reset was ~midnight Pacific
Time based on general knowledge, but bill_13 succeeded a few hours after
first hitting the 429 quota error). Not something to rely on/assume for
future planning, but good to know it isn't necessarily a full 24h wait.

## FINAL RESULTS (all 39 extractions successful, clean eval run)

**Overall accuracy**: Gemini 85.9%, Groq 80.8%, Mistral 71.8%.

Per-field breakdown (%):

| Field       | Gemini | Groq | Mistral |
| ----------- | ------ | ---- | ------- |
| vendor      | 76.9   | 84.6 | 84.6    |
| bill_number | 76.9   | 76.9 | 61.5    |
| date        | 84.6   | 53.8 | 38.5    |
| amount      | 100.0  | 92.3 | 69.2    |
| currency    | 92.3   | 92.3 | 100.0   |
| gst_details | 84.6   | 84.6 | 76.9    |

Key takeaways:

- **Gemini is the clear overall leader**, and specifically hits a perfect
  100% on amount — the single most important field for real accounting/
  bookkeeping use. Also strongest on date (84.6%), the field every model
  struggles with most.
- **Groq and Mistral tie on vendor** (84.6%, both beat Gemini here) —
  interesting, since Gemini still wins overall; no single model dominates
  every field.
- **Date remains the hardest field for every model**, worst for Mistral
  (38.5%) and Groq (53.8%). Handwritten digit sequences are genuinely
  more ambiguous than words — good example to include in the write-up
  (bill_01's date was read differently by more than one model; bill_03
  caused Groq's reasoning to spiral entirely due to messy handwritten
  amounts, see failure-mode note above).
- **Mistral is weakest overall**, particularly on date and amount — the
  two fields that matter most for actual bookkeeping accuracy.

**Cost** (real usage data: 13/13 Mistral, 13/13 Groq, 1/13 Gemini — see
limitation note below):

| Model   | Avg cost/bill | Extrapolated to 100 bills |
| ------- | ------------- | ------------------------- |
| Mistral | $0.000073     | $0.0073                   |
| Gemini  | $0.000442     | $0.0442                   |
| Groq    | $0.002726     | $0.2726                   |

- **Groq is clearly the most expensive per bill** despite being a
  "free-tier" option — its $3.00/M output pricing plus the extra output
  tokens spent on visible `<think>` reasoning add up. Worth noting: this
  is Groq's real, complete cost (13/13 real usage), so this comparison
  point is solid.
- **Mistral is by far the cheapest.**
- **Gemini's cost figure is NOT fully reliable** — only 1 of 13 files
  (the bill_13 retry) has real usage data; the other 12 predate the
  usage-logging fix and are estimated from output text length only,
  missing image-input cost entirely. Gemini's true cost is likely higher
  than $0.000442/bill shown here. State this explicitly as a limitation
  in the write-up rather than presenting it as a clean number — don't
  claim "Gemini beats Groq on cost" with full confidence; the accuracy
  gap is well established, the cost comparison specifically involving
  Gemini is not yet, on this data.

**Bottom-line recommendation (draft, refine in Phase 6)**: for a
production handwritten-bill pipeline, Gemini looks like the best default
given its accuracy lead, especially on amount — the highest-stakes field.
Groq's advantage on vendor name doesn't offset being 3-6x pricier per bill
and having a real "fails to answer" failure mode Gemini/Mistral don't
show. Mistral is the cheapest by a wide margin but the accuracy trade-off
(especially on date) is significant enough that it's a harder sell unless
cost is the dominant constraint.

## Phase 5 — Zoho Books integration progress

- OAuth setup completed successfully on first real attempt. Full flow
  confirmed working: Self Client (client_id + client_secret) → one-time
  browser-generated authorization code → exchanged for refresh_token →
  refresh_token used to mint a fresh access_token programmatically (this
  last step is what the real script will do every time it runs, no more
  manual browser steps needed going forward).

- **Region matters**: account is India-based, so used `.in` domain
  throughout, not `.com` — `accounts.zoho.in` for OAuth token exchange,
  `www.zohoapis.in` for actual Books API calls (`api_domain` returned
  directly in the token response, confirmed this explicitly rather than
  assuming).

- Organization created: "Taxor Test Org", India, INR, org_id
  `60081141334`. All five needed credentials now live in `.env`:
  `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`,
  `ZOHO_API_DOMAIN`, `ZOHO_ORGANIZATION_ID`.

- **Design decision**: Zoho's Expenses API requires every expense to be
  mapped to a chart-of-accounts expense category (not just freeform
  vendor/amount/date). Decided to use a single generic default account
  (e.g. "Miscellaneous Expense" or similar) for all test entries, rather
  than trying to have a model infer/assign categories per bill — the goal
  here is proving the extraction-to-books pipeline works end-to-end, not
  building real categorized bookkeeping. Worth a one-line mention in the
  write-up: "category assignment was out of scope; a production version
  would likely want the model to also suggest an expense category."

- **Plan**: push 3-4 already-extracted bills (using Gemini's results,
  since it's the most accurate model per Phase 4) into Zoho as real
  expense entries, to demonstrate the full pipeline (image → extraction →
  eval → real accounting system) works, not just extraction in isolation.

## To revisit later (Phase 4 / write-up)

- Rerun eval_all.py after retrying groq_bill_08 and gemini_bill_13, update
  numbers above with the clean run.
- Double check the 0.75 vendor fuzzy threshold still feels right once all
  13 bills are clean — currently a judgment call, not rigorously tuned.
- Note preview-model caveat for Groq explicitly in the final
  recommendation section (see model/setup quirks above).
- Still need: cost calculation per model (token usage × pricing), Zoho
  Books integration (Phase 5), final write-up (Phase 6).
