import json

from sam.classification_completeness import apply_completeness_adjustments, sanitize_provisional_narrative
from sam.rgi import RgiPipeline
from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index


class C:
    def __init__(self, content: str) -> None:
        self.page_content = content


with open("sam/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)
set_tariff_label_index(build_tariff_label_index([C(c) for c in chunks]))

source = (
    "sac de voyage haut de gamme destine au transport d'effets personnels "
    "composer de 100% de cuir provenant d'italie et acheter a 450000 dollars"
)

# Simulate LLM suggesting wrong code 4202.22.90
item = {
    "hs_code": "4202.22.90.00",
    "chapter": "42",
    "description": source,
    "confidence": 90,
    "justification": "RGI 1 sac de voyage",
}
pipeline = RgiPipeline().run(source, [item])
print("=== PIPELINE ===")
for r in pipeline.applied_rules:
    print("+", r.rule, r.reason[:80])
for r in pipeline.not_applied_rules:
    print("-", r.rule, r.reason[:80])

apply_completeness_adjustments(item, source_text=source)
print("\n=== FINAL ===")
print("hs:", item.get("hs_code"))
print("suggested:", item.get("hs_code_suggested"))
print("missing:", item.get("missing_fields"))
narr = sanitize_provisional_narrative("x", [item])
print("\n=== NARRATIVE (first 800) ===")
print(narr[:800])
