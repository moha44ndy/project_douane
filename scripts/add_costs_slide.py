"""Ajoute le contenu coûts sur la slide 8 de Logiciel-douane_vF.pptx."""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt

PPTX_PATH = Path(r"c:\MAMP\htdocs\Logiciel-douane_vF.pptx")
SLIDE_INDEX = 7  # slide 8 (0-based)

DARK = RGBColor(0x06, 0x2B, 0x50)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

PUNCHLINE = (
    "Une erreur de classification peut coûter plusieurs centaines de milliers de FCFA, "
    "alors qu'une analyse Mosam coûte moins de 30 FCFA."
)


def _set_text(shape, text: str, *, font_name: str, size_pt: float, bold: bool = False, color=None):
    tf = shape.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _clone_text_style(source_shape, target_shape, text: str):
    src_p = source_shape.text_frame.paragraphs[0]
    src_run = src_p.runs[0] if src_p.runs else None
    tf = target_shape.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    if src_run is not None:
        run.font.name = src_run.font.name
        run.font.size = src_run.font.size
        run.font.bold = src_run.font.bold
        if src_run.font.color and src_run.font.color.type:
            run.font.color.rgb = src_run.font.color.rgb


def _add_punchline(cost_slide, prs: Presentation) -> None:
    ref_slide = prs.slides[4]
    ref_shape = next(
        s for s in ref_slide.shapes if hasattr(s, "text") and "Coût potentiel total" in s.text
    )
    box = cost_slide.shapes.add_textbox(
        ref_shape.left,
        4680000,
        ref_shape.width + 800000,
        ref_shape.height + 80000,
    )
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = PUNCHLINE
    ref_run = ref_shape.text_frame.paragraphs[0].runs[0]
    run.font.name = ref_run.font.name
    run.font.size = ref_run.font.size
    run.font.bold = ref_run.font.bold
    run.font.color.rgb = ref_run.font.color.rgb


def main() -> None:
    prs = Presentation(str(PPTX_PATH))
    roi_slide = prs.slides[8]
    cost_slide = prs.slides[SLIDE_INDEX]

    for shape in list(cost_slide.shapes):
        sp = shape._element
        sp.getparent().remove(sp)

    label_src = roi_slide.shapes[1]
    title_src = roi_slide.shapes[2]
    subtitle_src = roi_slide.shapes[3]
    num_src = roi_slide.shapes[5]
    item_title_src = roi_slide.shapes[6]
    item_body_src = roi_slide.shapes[7]
    callout_title_src = roi_slide.shapes[17]
    callout_body_src = roi_slide.shapes[18]
    callout_footer_src = roi_slide.shapes[20] if len(roi_slide.shapes) > 20 else roi_slide.shapes[19]

    def add_box(left, top, width, height):
        return cost_slide.shapes.add_textbox(left, top, width, height)

    label = add_box(label_src.left, label_src.top, label_src.width, label_src.height)
    _clone_text_style(label_src, label, "COÛTS D'EXPLOITATION")

    title = add_box(title_src.left, title_src.top, title_src.width, title_src.height)
    _clone_text_style(title_src, title, "Un modèle économique maîtrisé")

    subtitle = add_box(subtitle_src.left, subtitle_src.top, subtitle_src.width, subtitle_src.height)
    _clone_text_style(subtitle_src, subtitle, "Estimation basée sur GPT-5 et l'architecture Mosam actuelle")

    items = [
        (
            "~0,02 $",
            "Par classification — fiche détaillée",
            "Dossier Excel ou description complète : moteur TEC local + 1 appel IA (~12 FCFA / produit).",
        ),
        (
            "~0,05 $",
            "Par classification — saisie courte",
            "Nom commercial ou référence : identification web + classification (~30 FCFA / produit).",
        ),
        (
            "~5 $",
            "Pour 100 classifications / mois",
            "Usage typique pilote (mix fiches détaillées + saisies courtes) — soit ~3 000 FCFA / mois IA.",
        ),
    ]

    num_positions = [roi_slide.shapes[5], roi_slide.shapes[9], roi_slide.shapes[13]]
    title_positions = [roi_slide.shapes[6], roi_slide.shapes[10], roi_slide.shapes[14]]
    body_positions = [roi_slide.shapes[7], roi_slide.shapes[11], roi_slide.shapes[15]]

    for idx, (num_text, item_title, item_body) in enumerate(items):
        nbox = add_box(
            num_positions[idx].left,
            num_positions[idx].top,
            num_positions[idx].width,
            num_positions[idx].height,
        )
        _clone_text_style(num_src, nbox, num_text)

        tbox = add_box(
            title_positions[idx].left,
            title_positions[idx].top,
            title_positions[idx].width,
            title_positions[idx].height,
        )
        _clone_text_style(item_title_src, tbox, item_title)

        bbox = add_box(
            body_positions[idx].left,
            body_positions[idx].top,
            body_positions[idx].width,
            body_positions[idx].height,
        )
        _clone_text_style(item_body_src, bbox, item_body)

    callout_bg = add_box(
        callout_title_src.left - 91440,
        callout_title_src.top - 91440,
        callout_title_src.width + 182880,
        callout_footer_src.top + callout_footer_src.height - callout_title_src.top + 182880,
    )
    callout_bg.fill.solid()
    callout_bg.fill.fore_color.rgb = DARK
    callout_bg.line.fill.background()

    ct = add_box(
        callout_title_src.left,
        callout_title_src.top,
        callout_title_src.width,
        callout_title_src.height,
    )
    _set_text(
        ct,
        "Coût marginal négligeable face au risque",
        font_name="Crimson Pro Bold",
        size_pt=10,
        bold=True,
        color=WHITE,
    )

    cb = add_box(
        callout_body_src.left,
        callout_body_src.top,
        callout_body_src.width,
        callout_body_src.height + 120000,
    )
    _set_text(
        cb,
        "Infrastructure cloud pilote (API, frontend, base de données) : 0 à 30 $/mois.\n"
        "Moteur TEC, RGI et tarifs : traitement local, sans surcoût IA.\n"
        "Le cache des requêtes identiques réduit le coût IA à 0 $.",
        font_name="Open Sans",
        size_pt=8.5,
        color=WHITE,
    )

    _add_punchline(cost_slide, prs)

    prs.save(str(PPTX_PATH))
    print(f"Slide {SLIDE_INDEX + 1} mise à jour : {PPTX_PATH}")


if __name__ == "__main__":
    main()
