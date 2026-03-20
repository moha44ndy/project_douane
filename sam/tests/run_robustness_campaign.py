import sys
import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from pypdf import PdfReader
import io

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sam.api import _extract_items_from_csv, _extract_items_from_pdf, _extract_items_from_txt


@dataclass
class ExtractionResult:
    ok: bool
    ms: float
    effective_query_len: int | None = None
    items_len: int | None = None
    items_sample: list[str] | None = None
    error: str | None = None
    stability_same_as_second_run: bool | None = None


def _minimal_pdf_bytes(text: str) -> bytes:
    """
    Construit un PDF minimal pour que `pypdf` puisse extraire du texte.

    Remarque : on génère la table xref avec offsets calculés dynamiquement.
    """
    # ASCII only; `pypdf` extrait mieux dans ce cas.
    safe = (text or "").encode("ascii", "ignore").decode("ascii")
    stream_text = safe.replace("(", "[").replace(")", "]")
    content_stream = f"BT /F1 12 Tf 72 720 Td ({stream_text}) Tj ET"
    stream_bytes = content_stream.encode("ascii")

    objects: list[str] = []
    # 1: Catalog
    objects.append("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj")
    # 2: Pages
    objects.append("2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj")
    # 3: Page
    objects.append(
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj"
    )
    # 4: Font
    objects.append("4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj")
    # 5: Content stream
    objects.append(
        f"5 0 obj<< /Length {len(stream_bytes)} >>stream\n{content_stream}\nendstream endobj"
    )

    header = "%PDF-1.4\n"
    offsets: list[int] = []
    body = ""
    # Offsets commencent apres header
    cursor = len(header.encode("ascii"))
    for obj in objects:
        offsets.append(cursor)
        b = obj.encode("ascii")
        body += obj + "\n"
        cursor += len(b) + 1  # + '\n'

    startxref = len((header + body).encode("ascii"))
    size = len(objects) + 1  # + object 0

    xref_lines = ["xref", f"0 {size}", "0000000000 65535 f "]
    for off in offsets:
        xref_lines.append(f"{off:010d} 00000 n ")
    xref = "\n".join(xref_lines) + "\n"

    trailer = f"trailer<< /Size {size} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF"
    pdf = header + body + xref + trailer
    return pdf.encode("ascii")


def _run_twice_stability(fn):
    first = fn()
    second = fn()
    # Ne compare que le contenu (effective_query, items) et pas les temps.
    same = first[:2] == second[:2]
    return first, same


def _extract_txt_case(name: str, content: str) -> ExtractionResult:
    def run():
        t0 = time.perf_counter()
        effective_query, items = _extract_items_from_txt(content, max_items=200)
        ms = (time.perf_counter() - t0) * 1000
        return effective_query, items, ms

    (effective_query_1, items_1, ms1), same = _run_twice_stability(run)
    items_sample = items_1[:8]
    return ExtractionResult(
        ok=True,
        ms=ms1,
        effective_query_len=len(effective_query_1 or ""),
        items_len=len(items_1),
        items_sample=items_sample,
        stability_same_as_second_run=same,
    )


def _extract_csv_case(name: str, content: str) -> ExtractionResult:
    def run():
        t0 = time.perf_counter()
        effective_query, items = _extract_items_from_csv(content, max_items=200)
        ms = (time.perf_counter() - t0) * 1000
        return effective_query, items, ms

    (effective_query_1, items_1, ms1), same = _run_twice_stability(run)
    items_sample = items_1[:8]
    return ExtractionResult(
        ok=True,
        ms=ms1,
        effective_query_len=len(effective_query_1 or ""),
        items_len=len(items_1),
        items_sample=items_sample,
        stability_same_as_second_run=same,
    )


def _extract_pdf_case(name: str, text: str) -> ExtractionResult:
    pdf_bytes = _minimal_pdf_bytes(text)

    def run():
        t0 = time.perf_counter()
        effective_query, items = _extract_items_from_pdf(
            pdf_bytes, max_items=200, max_chars=20000
        )
        ms = (time.perf_counter() - t0) * 1000
        return effective_query, items, ms

    try:
        # sanity: pypdf can read
        reader = PdfReader(io.BytesIO(pdf_bytes))
        _ = len(reader.pages)
    except Exception as e:
        return ExtractionResult(ok=False, ms=0.0, error=f"pypdf read failed: {e}")

    (effective_query_1, items_1, ms1), same = _run_twice_stability(run)
    return ExtractionResult(
        ok=True,
        ms=ms1,
        effective_query_len=len(effective_query_1 or ""),
        items_len=len(items_1),
        items_sample=items_1[:8],
        stability_same_as_second_run=same,
    )


def main() -> None:
    run_endpoint_tests = os.getenv("RUN_ENDPOINT_TESTS", "0") == "1"
    endpoint_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    out: dict[str, object] = {"started_at": time.time(), "cases": {}, "endpoint_tests": {}}

    # TXT edge cases
    txt_content = "\n".join(
        [
            "Produit | Qté | Valeur | Origine",
            "Ordinateur portable i7 | 5 | 1500000 | chine",
            "telephone android 5g | 12 | 350000 | vietnam",
            "",
            "origine Chine, valeur 500000",  # bruit metadata
            "2 cartons de 12 ordinateurs",
            "3 lots x 5 bouteilles d'eau",
            "taxi + moto",
            "Qte | Produit | Valeur | Origine",  # header bruit
            "0 ordinateur",
            "-5 ordinateurs",
            "~20 ordinateurs",
            "environ 14 ordinateurs",
            "approx 11 ordinateurs",
        ]
    )

    out["cases"]["txt_edge"] = asdict(_extract_txt_case("txt_edge", txt_content))

    txt_semicolon_table = "\n".join(
        [
            "Produit;Qté;Valeur;Origine",
            "PC gamer;2;2200000;usa",
            "cannettes d eau;4;2400;chine",
            "bouteilles d'eau;3;1200;chine",
            "",
            "Origine : chine",
            "valeur=500000",
            "qte 12",
            "ordinateur portable i7 x 5",
            "ordinateur + téléphone; taxi",
        ]
    )
    out["cases"]["txt_semicolon_table_edge"] = asdict(
        _extract_txt_case("txt_semicolon_table_edge", txt_semicolon_table)
    )

    txt_multi_sep = "\n".join(
        [
            "ordinateur + telephone + taxi",
            "telephone, quantite 6, origine chine, valeur 300000",
            "taxi; moto",
            "sac a main, origine france, valeur 120000",
            "sac à main comptant 10 exemplaires",
            "boutaille deau",  # typo attendu -> n'est pas géré ici (on teste juste l'extraction)
        ]
    )
    out["cases"]["txt_multi_sep_edge"] = asdict(
        _extract_txt_case("txt_multi_sep_edge", txt_multi_sep)
    )

    # CSV edge cases
    csv_semicolon = "\n".join(
        [
            "Produit;Qté;Valeur;Origine",
            '"Ordinateur portable i7";5;1500000;chine',
            'telephone android 5g;12;350000;vietnam',
            "\"bouteilles d'eau\";3;2400;chine",
        ]
    )
    out["cases"]["csv_semicolon_edge"] = asdict(_extract_csv_case("csv_semicolon", csv_semicolon))

    csv_comma_no_header = "\n".join(
        [
            "Ordinateur portable i7,5,1500000,chine",
            "telephone android 5g,12,350000,vietnam",
        ]
    )
    out["cases"]["csv_comma_no_header"] = asdict(_extract_csv_case("csv_comma_no_header", csv_comma_no_header))

    csv_weird_quotes = "\n".join(
        [
            "libellé;quantité;prix;origine",
            '"sac a main";"7";"80000";"italie"',
            "\"bouteilles d'eau\";\"2\";\"2400\";\"chine\"",
        ]
    )
    # Note: on laisse les guillemets/échappements pour tester le sniffing + split simple.
    out["cases"]["csv_weird_quotes_edge"] = asdict(
        _extract_csv_case("csv_weird_quotes_edge", csv_weird_quotes)
    )

    # PDF edge case: minimal pdf with "ordinateur" in text
    out["cases"]["pdf_minimal_text"] = asdict(_extract_pdf_case("pdf_minimal_text", "ordinateur 2 pcs"))

    # Load/perf stability: re-run a few extraction loops (no LLM)
    load_repeats = int(os.getenv("LOAD_REPEATS", "10"))
    load_t0 = time.perf_counter()
    for _ in range(load_repeats):
        _extract_items_from_txt(txt_content, max_items=200)
    load_ms = (time.perf_counter() - load_t0) * 1000 / max(1, load_repeats)
    out["load_tests"] = {
        "txt_edge_avg_ms": load_ms,
        "repeats": load_repeats,
    }

    # Stability over several runs (extraction only)
    extraction_ms = [out["cases"][k]["ms"] for k in out["cases"] if out["cases"][k].get("ok")]
    out["perf_summary_ms"] = {
        "extraction_cases": len(extraction_ms),
        "min_ms": min(extraction_ms) if extraction_ms else None,
        "max_ms": max(extraction_ms) if extraction_ms else None,
    }

    # Optional endpoint tests (can be slow due to LLM)
    if run_endpoint_tests:
        try:
            for i in range(3):
                query = "ordinateur x 2\ntelephone android 5g\nbouteilles d'eau x 3"
                t0 = time.perf_counter()
                r = requests.post(
                    f"{endpoint_url}/classify",
                    json={"query": query},
                    timeout=180,
                )
                r.raise_for_status()
                ms = (time.perf_counter() - t0) * 1000
                data = r.json()
                raw = data.get("raw", "")
                # verify it is valid JSON
                json.loads(raw)
                out["endpoint_tests"][f"classify_run_{i}"] = {"ms": ms, "ok": True}
        except Exception as e:
            out["endpoint_tests"]["error"] = str(e)

        # /classify/file TXT only (cheap-ish compared to PDF)
        try:
            txt_path = Path("sam/tests/tmp_fixture_edge.txt")
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            txt_path.write_text(txt_content, encoding="utf-8")
            t0 = time.perf_counter()
            with open(txt_path, "rb") as f:
                r = requests.post(
                    f"{endpoint_url}/classify/file",
                    files={"file": (txt_path.name, f, "text/plain")},
                    data={"max_items": 60, "batch_size": 10, "max_chars": 20000},
                    timeout=180,
                )
            r.raise_for_status()
            ms = (time.perf_counter() - t0) * 1000
            data = r.json()
            obj = json.loads(data["raw"])
            out["endpoint_tests"]["classify_file_txt"] = {"ms": ms, "classifications_len": len(obj.get("classifications", []))}
        except Exception as e:
            out["endpoint_tests"]["classify_file_txt_error"] = str(e)

    out["finished_at"] = time.time()

    out_dir = Path("sam/tests/tmp_reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"robustness_report_{int(time.time())}.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()

