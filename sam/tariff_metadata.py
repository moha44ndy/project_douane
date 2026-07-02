"""Libelles officiels complets sections/chapitres/positions TEC."""

from __future__ import annotations

from .tariff_labels import lookup_position_label
from .tariff_notes import get_chapter_title

# Titres complets des sections SH (nomenclature CEDEAO/SH)
HS_SECTION_FULL_NAMES: dict[str, str] = {
    "I": "Animaux vivants et produits du regne animal",
    "II": "Produits du regne vegetal",
    "III": "Graisses et huiles animales, vegetales ou d'origine minerale; cires",
    "IV": "Produits des industries alimentaires; boissons, liquides alcooliques et vinaigres; tabacs",
    "V": "Produits mineraux",
    "VI": "Produits des industries chimiques ou des industries connexes",
    "VII": "Matières plastiques et ouvrages en ces matieres; caoutchouc et ouvrages en caoutchouc",
    "VIII": (
        "Peaux, cuirs, pelleteries et ouvrages en ces matieres; "
        "articles de sellerie ou de bourrellerie; "
        "articles de voyage, sacs a main et contenants similaires; "
        "ouvrages en boyaux"
    ),
    "IX": "Bois, charbon de bois et ouvrages en bois; liege et ouvrages en liege; "
    "ouvrages de sparterie ou de vannerie",
    "X": "Pates de bois ou d'autres matieres fibreuses cellulosiques; "
    "papier ou carton a recycler; papier et carton",
    "XI": "Matières textiles et ouvrages en ces matieres",
    "XII": "Chaussures, coiffures, parapluies, parasols, cannes, fouets, cravaches",
    "XIII": "Ouvrages en pierres, platre, ciment, amiante, mica ou matieres analogues; "
    "produits ceramiques; verre et ouvrages en verre",
    "XIV": "Perles fines ou de culture, pierres gemmes, metaux precieux, plaques de metal precieux",
    "XV": "Metaux communs et ouvrages en ces metaux",
    "XVI": "Machines et appareils, materiel electrique; parties; appareils d'enregistrement",
    "XVII": "Materiel de transport",
    "XVIII": "Instruments et appareils d'optique, photographie, cinematographie, mesure, controle; "
    "horlogerie; instruments de musique",
    "XIX": "Armes, munitions et leurs parties et accessoires",
    "XX": "Marchandises et produits divers",
    "XXI": "Objets d'art, de collection ou d'antiquite",
}

def get_full_section_name(section_roman: str, fallback: str = "") -> str:
    return HS_SECTION_FULL_NAMES.get(section_roman.strip().upper(), fallback or section_roman)


def get_full_chapter_name(chapter: str | int, fallback: str = "") -> str:
    try:
        ch = int(str(chapter).lstrip("0") or "0")
    except ValueError:
        return fallback
    title = get_chapter_title(ch)
    if title:
        return title
    return fallback or f"Chapitre {ch:02d}"


def get_position_heading(hs_position: str) -> str:
    """Libelle TEC de la position, lu depuis l'index des chunks (pas de libelle en dur)."""
    normalized = (hs_position or "").strip()
    if not normalized:
        return ""
    for candidate in (
        normalized,
        f"{normalized}.00.00",
        f"{normalized}.00",
    ):
        label = lookup_position_label(candidate)
        if label:
            return label
    parts = normalized.split(".")
    if len(parts) >= 2:
        return lookup_position_label(f"{parts[0]}.{parts[1]}") or ""
    return ""
