import json
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
FILE_PATH = Path(os.getenv("LIMITS_FILE", "sam/test_multi_produits.txt"))

RUNS_PER_QUERY = int(os.getenv("RUNS_PER_QUERY", "3"))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "500"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
MAX_CHARS = int(os.getenv("MAX_CHARS", "20000"))


HS_CODE_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}$")


@dataclass
class RunResult:
    ok: bool
    ms: float
    status_code: int | None = None
    error: str | None = None

    json_ok: bool | None = None
    narrative_ok: bool | None = None
    classifications_len: int | None = None

    hs_codes: list[str] | None = None
    invalid_hs_format_count: int | None = None
    non_renseignes_count: int | None = None
    chapter_mismatch_count: int | None = None

    confidence_min: int | None = None
    confidence_avg: float | None = None


def _is_non_renseigne(v: object) -> bool:
    if v is None:
        return True
    s = str(v)
    return "Non renseign" in s


def _validate_raw(raw: object) -> tuple[bool, dict]:
    if not isinstance(raw, str):
        return False, {"reason": "raw_not_str"}
    try:
        obj = json.loads(raw)
    except Exception as e:
        return False, {"reason": "json_parse_error", "detail": str(e)[:200]}
    if not isinstance(obj, dict):
        return False, {"reason": "json_not_dict"}

    narrative = obj.get("narrative")
    narrative_ok = isinstance(narrative, str) and bool(narrative.strip())
    classifications = obj.get("classifications")
    classifications_ok = isinstance(classifications, list)
    return True, {
        "narrative_ok": narrative_ok,
        "classifications_ok": classifications_ok,
        "obj": obj,
    }


def _analyze_classifications(classifications: object) -> dict:
    if not isinstance(classifications, list):
        return {}

    hs_codes: list[str] = []
    invalid_hs_format_count = 0
    non_renseignes_count = 0
    chapter_mismatch_count = 0
    confidences: list[int] = []

    for item in classifications:
        if not isinstance(item, dict):
            continue
        hs = item.get("hs_code")
        chapter = item.get("chapter")
        conf = item.get("confidence")

        if isinstance(conf, (int, float)):
            confidences.append(int(conf))

        if hs is None or _is_non_renseigne(hs):
            non_renseignes_count += 1
            continue

        if not isinstance(hs, str) or not HS_CODE_RE.match(hs):
            invalid_hs_format_count += 1
            continue

        hs_codes.append(hs)

        hs_chapter = hs.split(".", 1)[0][:2]  # "8471..." -> "84"
        if isinstance(chapter, str) and chapter.strip() and chapter.strip() != hs_chapter:
            chapter_mismatch_count += 1

    confidence_min = min(confidences) if confidences else None
    confidence_avg = sum(confidences) / len(confidences) if confidences else None

    return {
        "hs_codes": hs_codes,
        "invalid_hs_format_count": invalid_hs_format_count,
        "non_renseignes_count": non_renseignes_count,
        "chapter_mismatch_count": chapter_mismatch_count,
        "confidence_min": confidence_min,
        "confidence_avg": confidence_avg,
    }


def _multiset(l: list[str]) -> list[str]:
    return sorted([x for x in l if isinstance(x, str)])


def main() -> None:
    if not FILE_PATH.exists():
        raise SystemExit(f"File not found: {FILE_PATH}")

    out_dir = Path("sam/tests/tmp_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"classification_limits_report_{int(time.time())}.json"

    raw_bytes = FILE_PATH.read_bytes()
    file_tuple = (FILE_PATH.name, raw_bytes, "text/plain")

    report: dict = {
        "api_base_url": API_BASE_URL,
        "limits_file": str(FILE_PATH),
        "runs_per_query": RUNS_PER_QUERY,
        "max_items": MAX_ITEMS,
        "batch_size": BATCH_SIZE,
        "max_chars": MAX_CHARS,
        "started_at": time.time(),
        "runs": [],
    }

    for i in range(RUNS_PER_QUERY):
        url = f"{API_BASE_URL}/classify/file"
        payload_data = {"max_items": MAX_ITEMS, "batch_size": BATCH_SIZE, "max_chars": MAX_CHARS}
        t0 = time.perf_counter()
        r = RunResult(ok=False, ms=0.0)
        try:
            resp = requests.post(url, files={"file": file_tuple}, data=payload_data, timeout=300)
            r.status_code = resp.status_code
            r.ms = (time.perf_counter() - t0) * 1000
            if resp.status_code >= 400:
                r.error = f"http_{resp.status_code}"
                report["runs"].append(asdict(r))
                continue

            data = resp.json()
            raw = data.get("raw")
            ok, details = _validate_raw(raw)
            r.json_ok = ok
            if not ok:
                r.error = details.get("reason")
                report["runs"].append(asdict(r))
                continue

            obj = details["obj"]
            r.narrative_ok = details["narrative_ok"]
            classifications = obj.get("classifications")
            r.classifications_len = len(classifications) if isinstance(classifications, list) else None

            analysis = _analyze_classifications(classifications)
            r.hs_codes = analysis.get("hs_codes")
            r.invalid_hs_format_count = analysis.get("invalid_hs_format_count")
            r.non_renseignes_count = analysis.get("non_renseignes_count")
            r.chapter_mismatch_count = analysis.get("chapter_mismatch_count")
            r.confidence_min = analysis.get("confidence_min")
            r.confidence_avg = analysis.get("confidence_avg")

            r.ok = True
        except Exception as e:
            r.ms = (time.perf_counter() - t0) * 1000
            r.error = str(e)[:300]
        finally:
            report["runs"].append(asdict(r))

    # Summary metrics
    ok_runs = [rr for rr in report["runs"] if rr.get("ok") is True]
    hs_multis = []
    for rr in ok_runs:
        hs_multis.append(_multiset(rr.get("hs_codes") or []))

    exact_match_ratio = 0.0
    if hs_multis:
        first = hs_multis[0]
        exact = sum(1 for x in hs_multis if x == first)
        exact_match_ratio = exact / len(hs_multis)

    non_renseignes_avg = (
        sum(rr.get("non_renseignes_count") or 0 for rr in ok_runs) / len(ok_runs) if ok_runs else None
    )
    invalid_hs_avg = (
        sum(rr.get("invalid_hs_format_count") or 0 for rr in ok_runs) / len(ok_runs) if ok_runs else None
    )
    chapter_mismatch_avg = (
        sum(rr.get("chapter_mismatch_count") or 0 for rr in ok_runs) / len(ok_runs) if ok_runs else None
    )

    report["summary"] = {
        "ok_runs": len(ok_runs),
        "total_runs": RUNS_PER_QUERY,
        "exact_hs_multiset_match_ratio": exact_match_ratio,
        "avg_non_renseignes_count": non_renseignes_avg,
        "avg_invalid_hs_format_count": invalid_hs_avg,
        "avg_chapter_mismatch_count": chapter_mismatch_avg,
    }

    report["finished_at"] = time.time()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()

