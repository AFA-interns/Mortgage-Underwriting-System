# ruff: noqa: E401, E402
"""Score name-pair labels against the real fuzzy matcher.
Usage (from backend/):  python app/compliance/compliance_eval/run_names.py [names_csv]
Defaults to data/names.csv next to this script."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
BACKEND = next(p for p in HERE.parents if (p / 'app' / 'compliance').is_dir())   # finds backend/ wherever this folder lives
csv_path = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data" / "names.csv")
sys.path.insert(0, str(BACKEND))
import pandas as pd
from rapidfuzz import fuzz
from app.compliance.identity_consistency import _names_match
df = pd.read_csv(csv_path, keep_default_na=False)
T = 90
df["score"] = [fuzz.token_sort_ratio(a.lower(), b.lower()) for a, b in zip(df.name_a, df.name_b)]
df["matcher_says_same"] = [_names_match(a, b, T) for a, b in zip(df.name_a, df.name_b)]
# positive class for the compliance flag = "mismatch raised" = matcher says different
df["flag_raised"] = ~df.matcher_says_same
df["should_flag"] = df.label == "different_person"
tp = int((df.flag_raised & df.should_flag).sum()); fn = int((~df.flag_raised & df.should_flag).sum())
fp = int((df.flag_raised & ~df.should_flag).sum()); tn = int((~df.flag_raised & ~df.should_flag).sum())
P = tp/(tp+fp) if tp+fp else float("nan"); R = tp/(tp+fn); F = 2*P*R/(P+R)
print(f"threshold={T}  TP={tp} FN={fn} FP={fp} TN={tn}  precision={P:.3f} recall={R:.3f} F1={F:.3f}")
print("\nmisses (label vs matcher):")
for _, r in df[df.flag_raised != df.should_flag].iterrows():
    kind = "FALSE ALARM (same person flagged)" if r.flag_raised else "MISSED MISMATCH (different person passed)"
    print(f"  {r.pair_id} {kind}: '{r.name_a}' vs '{r.name_b}' pattern={r.pattern} score={r.score:.1f}")
print("\nscore by pattern (min / max):")
print(df.groupby(["label","pattern"]).score.agg(["count","min","max"]).round(1).to_string())
print("\nclosest calls to the threshold (|score-90|<=6):")
near = df[(df.score - T).abs() <= 6].sort_values("score")
for _, r in near.iterrows(): print(f"  {r.pair_id} {r.label:16s} {r.score:5.1f}  '{r.name_a}' vs '{r.name_b}'  ({r.pattern})")
print("\nthreshold sweep (precision/recall of mismatch flag):")
for t in [70,75,80,85,88,90,92,95]:
    fr = df.score < t
    tp=int((fr&df.should_flag).sum()); fn=int((~fr&df.should_flag).sum()); fp=int((fr&~df.should_flag).sum())
    p = tp/(tp+fp) if tp+fp else float('nan'); r_=tp/(tp+fn)
    print(f"  t={t}: precision={p:.3f} recall={r_:.3f}  FP={fp} FN={fn}")
