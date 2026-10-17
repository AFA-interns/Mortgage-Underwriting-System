# Property Valuation Agent evaluation metrics

Measurement only. Nothing here changes a valuation, a comparable-selection rule, or any tool in `app/tools/`, and nothing in `app.property_valuation.metrics` is imported by the agent.

- Source document: `Automated Valuation Model (AVM) — Evaluation Metrics.pdf` (repo root) - defines PPE10, PPE20, MdAPE, FSD, Coverage Rate for an AVM / property valuation agent.
- Code: `backend/app/property_valuation/metrics.py` (standard library only, pure functions)
- Benchmark runner: `backend/app/property_valuation/benchmark.py` (reads applications already stored, no manual export)
- Tests: `backend/tests/test_property_valuation_metrics.py` - each example is taken directly from the source PDF

**Status key** - **Now**: needs only applications already stored. **Later**: needs an actual transaction price per property, which this system does not record anywhere.

## Now - Coverage Rate

| Metric | Formula | Needs | Function |
|---|---|---|---|
| Coverage Rate | (applications with a produced valuation ÷ total applications) × 100 | Only what the agent itself already recorded (`estimated_value > 0`) | `coverage_rate` |

Coverage Rate also breaks down *which* source produced each valuation (`avnester` live listings / `scraped_db` / `local_db` median / none), reusing the `evidence` entry `property_valuation_node` already attaches to every run (`field: "estimated_value"`, `source: value_source`).

A model can be accurate on the properties it successfully values while still having limited coverage (the PDF's own example: 90% PPE20, 10% MdAPE, 45% Coverage) - so Coverage Rate matters even before accuracy can be measured at all.

## Later - needs an actual transaction price (not captured yet)

| Metric | Formula | Target shape | Function |
|---|---|---|---|
| PPE10 | % of (predicted, actual) pairs with absolute percentage error ≤ 10% | higher is better | `ppe_rate(pairs, 10)` |
| PPE20 | % of (predicted, actual) pairs with absolute percentage error ≤ 20% | higher is better | `ppe_rate(pairs, 20)` |
| MdAPE | median of `|predicted - actual| / actual × 100` across all pairs | lower is better | `mdape` |
| FSD | forecast uncertainty / variability around the point estimate | model-dependent | **not implemented** - see below |

`valuation_accuracy_report(pairs)` computes all three the moment real `(predicted, actual_transaction_price)` pairs exist, and returns `{"available": False, "reason": ...}` - never a fabricated number - until then. Every example in `test_property_valuation_metrics.py` reproduces the source PDF's own worked example (₹46L vs ₹50L → 8% error; errors 4/10/25/8/5% → MdAPE 8%; 700/1000 → Coverage 70%) so the maths is checked against the document, not just against itself.

**Why FSD is not implemented**: the source PDF is explicit that FSD "should be defined according to the [agent's] underlying statistical methodology" and "should not automatically be treated as the standard deviation of raw prediction errors unless that is how the model has been designed." This agent's valuation is a deterministic comparable-median calculation (AVnester listings, then the scraped comparables DB, then a local median fallback - see `property_valuation_node`), not a calibrated probabilistic model with its own uncertainty output. Reporting `stdev(errors)` as "FSD" would misrepresent it as the model's own confidence when it is really just post-hoc error spread over whatever labeled sample happens to exist. If/when the agent is extended to emit a real per-valuation uncertainty band, FSD can be added against that.

## What this system would need to capture

Nothing in the current schema records a property's actual closed-sale price. To make PPE10/PPE20/MdAPE real (not proposed - no migration made yet):

- An `actual_sale_price` (or `outcome_value`) field on the application, populated once the underlying loan closes and the property's real transaction price is known (same shape problem as `CREDIT_METRICS.md`'s missing `outcome_bad`).
- A process for collecting it after the fact - this is fundamentally a closed-loan outcome, not something available at underwriting time.

Until that exists, this document's "Later" section stays exactly that.
