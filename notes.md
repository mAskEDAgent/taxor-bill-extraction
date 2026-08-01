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

## To revisit later (Phase 4 / write-up)

- Decide + document the fuzzy-match threshold for vendor name comparison
  (e.g. similarity >= 0.8 = "correct") — needs a clear justification in
  the write-up, not just a number pulled from nowhere.
- Decide whether "ground truth blank + model returned null" should count
  as correct (leaning yes — both correctly recognized absence).
- Note preview-model caveat for Groq explicitly in the final
  recommendation section.
- gst_details scoring: switched from generic fuzzy string matching to     percentage-extraction matching, because verbose-but-correct answers (e.g. including GSTIN numbers) were being scored as "wrong" purely due to length/wording differences, not actual inaccuracy. Scoring now checks: (1) does presence/absence of GST agree, (2) if GST is present and ground truth specifies a rate, does at least one matching percentage appear in the model's answer.