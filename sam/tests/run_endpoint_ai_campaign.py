import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RUNS_PER_QUERY = int(os.getenv("RUNS_PER_QUERY", "3"))


@dataclass
class CallResult:
    ok: bool
    ms: float
    status_code: int | None = None
    error: str | None = None
    json_parse_ok: bool | None = None
    narrative_ok: bool | None = None
    classifications_ok: bool | None = None
    hs_codes: list[str] | None = None
    non_renseignes: int | None = None


def _validate_raw_response(raw: object) -> tuple[bool, dict]:
    """
    raw attendu : string JSON (contrat UI/backend).
    """
    if not isinstance(raw, str):
        return False, {"reason": "raw_not_str"}

    try:
        obj = json.loads(raw)
    except Exception as e:
        return False, {"reason": "json_parse_error", "detail": str(e)[:200]}

    if not isinstance(obj, dict):
        return False, {"reason": "json_not_dict"}

    narrative = obj.get("narrative")
    classifications = obj.get("classifications")

    narrative_ok = isinstance(narrative, str) and bool(narrative.strip())
    classifications_ok = isinstance(classifications, list)

    hs_codes: list[str] = []
    if classifications_ok:
        for item in classifications:
            if isinstance(item, dict):
                hs = item.get("hs_code")
                if isinstance(hs, str):
                    hs_codes.append(hs)

    non_renseignes = sum(1 for hs in hs_codes if (not hs) or ("Non renseign" in str(hs)))
    return True, {
        "narrative_ok": narrative_ok,
        "classifications_ok": classifications_ok,
        "hs_codes": hs_codes,
        "non_renseignes": non_renseignes,
    }


def _post_json(url: str, payload: dict, timeout_s: int) -> CallResult:
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json=payload, timeout=timeout_s)
        ms = (time.perf_counter() - t0) * 1000
        result = CallResult(ok=True, ms=ms, status_code=r.status_code)
        if r.status_code >= 400:
            result.ok = False
            result.error = f"http_{r.status_code}"
            return result

        data = r.json()
        raw = data.get("raw")
        ok, details = _validate_raw_response(raw)
        result.json_parse_ok = ok
        result.narrative_ok = details.get("narrative_ok") if ok else None
        result.classifications_ok = details.get("classifications_ok") if ok else None
        result.hs_codes = details.get("hs_codes") if ok else None
        result.non_renseignes = details.get("non_renseignes") if ok else None
        return result
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return CallResult(ok=False, ms=ms, error=str(e)[:300])


def _post_file_txt(url: str, content: str, form_data: dict, timeout_s: int) -> CallResult:
    t0 = time.perf_counter()
    try:
        # In-memory file
        r = requests.post(
            url,
            files={"file": ("test.txt", content.encode("utf-8", errors="ignore"), "text/plain")},
            data=form_data,
            timeout=timeout_s,
        )
        ms = (time.perf_counter() - t0) * 1000
        result = CallResult(ok=True, ms=ms, status_code=r.status_code)
        if r.status_code >= 400:
            result.ok = False
            result.error = f"http_{r.status_code}"
            return result

        data = r.json()
        raw = data.get("raw")
        ok, details = _validate_raw_response(raw)
        result.json_parse_ok = ok
        result.narrative_ok = details.get("narrative_ok") if ok else None
        result.classifications_ok = details.get("classifications_ok") if ok else None
        result.hs_codes = details.get("hs_codes") if ok else None
        result.non_renseignes = details.get("non_renseignes") if ok else None
        return result
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return CallResult(ok=False, ms=ms, error=str(e)[:300])


def _stability_score(runs: list[CallResult]) -> dict:
    """
    Score "stabilité" simplifié :
    - on compare la séquence des hs_codes (string) normalisée en multiset.
    - pour le projet, l'objectif est d'éviter les gros changements de code.
    """
    hs_lists = [r.hs_codes for r in runs if r.ok and r.hs_codes is not None]
    if not hs_lists:
        return {"runs_with_hs": 0, "exact_match_ratio": 0.0}

    first = hs_lists[0]
    first_sorted = sorted(first)
    exact = 0
    for hs in hs_lists:
        if sorted(hs) == first_sorted:
            exact += 1
    return {"runs_with_hs": len(hs_lists), "exact_match_ratio": exact / len(hs_lists)}


def main() -> None:
    out_dir = Path("sam/tests/tmp_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"endpoint_campaign_report_{int(time.time())}.json"

    # Scenarios (petits pour limiter le coût/latence).
    scenarios: list[dict] = [
        {
            "name": "multi_lines_basic",
            "endpoint": "/classify",
            "timeout_s": 90,
            "payload": {
                "query": "\n".join(
                    [
                        "ordinateur portable i7 | 5 | 1500000 | chine",
                        "telephone android 5g | 12 | 350000 | vietnam",
                        "sac a main cuir | 7 | 80000 | italie",
                    ]
                )
            },
        },
        {
            "name": "typos_and_separators",
            "endpoint": "/classify",
            "timeout_s": 90,
            "payload": {
                "query": "\n".join(
                    [
                        "2 ordianteur",
                        "1 bijous",
                        "3 cannete de eau",
                        "2 boutailles d eau",
                        "6 chevaux",
                        "ordinateur + telephone + taxi",
                    ]
                )
            },
        },
        {
            "name": "txt_file_mixed_noise",
            "endpoint": "/classify/file",
            "timeout_s": 120,
            "form_data": {"max_items": 80, "batch_size": 20, "max_chars": 20000},
            "file_content": "\n".join(
                [
                    "Produit | Qté | Valeur | Origine",
                    "Ordinateur portable i7 | 5 | 1500000 | chine",
                    "telephone android 5g | 12 | 350000 | vietnam",
                    "origine Chine, valeur 500000",
                    "2 cartons de 12 ordinateurs",
                    "telephone, quantite 6, origine chine, valeur 300000",
                    "sac à main",
                    "sac à main cuir | 7 | 80000 | italie",
                    "",
                    "3 lots x 5 bouteilles d'eau",
                    "5 cannette deau",
                    "2 cannettes d eau",
                    "4 packs * 6 ordinateurs",
                ]
            ),
        },
    ]

    scenarios_limit_raw = os.getenv("SCENARIOS_LIMIT", "").strip()
    scenarios_limit = int(scenarios_limit_raw) if scenarios_limit_raw else 0
    if scenarios_limit and scenarios_limit > 0:
        scenarios = scenarios[:scenarios_limit]

    report: dict = {
        "api_base_url": API_BASE_URL,
        "runs_per_query": RUNS_PER_QUERY,
        "started_at": time.time(),
        "scenarios": {},
    }

    for sc in scenarios:
        name = sc["name"]
        endpoint = sc["endpoint"]
        url = f"{API_BASE_URL}{endpoint}"
        timeout_s = sc.get("timeout_s", 180)

        runs: list[CallResult] = []
        scenario_error: str | None = None
        try:
            for _i in range(RUNS_PER_QUERY):
                if endpoint == "/classify":
                    payload = sc["payload"]
                    runs.append(_post_json(url, payload, timeout_s=timeout_s))
                else:
                    runs.append(
                        _post_file_txt(
                            url,
                            content=sc["file_content"],
                            form_data=sc["form_data"],
                            timeout_s=timeout_s,
                        )
                    )
        except Exception as e:
            scenario_error = str(e)[:300]

        successes = sum(1 for r in runs if r.ok)
        non_zeros = [
            r.non_renseignes for r in runs if r.ok and r.non_renseignes is not None
        ]
        non_avg = sum(non_zeros) / len(non_zeros) if non_zeros else None
        ms_vals = [r.ms for r in runs if r.ok]

        report["scenarios"][name] = {
            "endpoint": endpoint,
            "url": url,
            "success_runs": successes,
            "total_runs": RUNS_PER_QUERY,
            "avg_ms": (sum(ms_vals) / len(ms_vals)) if ms_vals else None,
            "min_ms": min(ms_vals) if ms_vals else None,
            "max_ms": max(ms_vals) if ms_vals else None,
            "avg_non_renseignes": non_avg,
            "stability": _stability_score(runs),
            "runs": [asdict(r) for r in runs],
            "scenario_error": scenario_error,
        }

    report["finished_at"] = time.time()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()

