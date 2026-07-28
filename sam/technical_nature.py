"""Tariff-neutral technical nature inference from observable product capabilities."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


@dataclass(frozen=True)
class TechnicalNature:
    name: str
    confidence: int
    matched_signals: tuple[str, ...]


@dataclass(frozen=True)
class _CapabilityProfile:
    name: str
    required_any: tuple[str, ...]
    supporting: tuple[str, ...]
    excluded: tuple[str, ...] = ()


# This ontology describes capabilities, not brands, models or tariff positions.
_CAPABILITY_PROFILES: tuple[_CapabilityProfile, ...] = (
    _CapabilityProfile(
        "optical data transceiver module",
        ("transceiver", "module optique", "liaison optique", "fibre optique"),
        ("transmission", "reception", "donnees", "ethernet", "100g", "40g", "10g"),
        ("camera", "imagerie"),
    ),
    _CapabilityProfile(
        "network data switching or routing equipment",
        ("commuter", "commutation", "switching", "router", "routeur", "trafic reseau"),
        ("ethernet", "reseau", "donnees", "transmettre", "ports", "pare feu", "firewall"),
    ),
    _CapabilityProfile(
        "digital video or thermal imaging camera",
        ("camera", "imagerie", "capturer des images", "enregistrer des images"),
        ("video", "numerique", "thermique", "multisenseur", "surveillance", "reseau ip", "optique"),
        ("cinematographique sur film",),
    ),
    _CapabilityProfile(
        "complete data storage system or storage unit",
        (
            "baie de stockage",
            "storage array",
            "administrer des donnees",
            "unite de stockage",
            "stockage en reseau",
            "nas",
            "san",
        ),
        ("serveur", "systeme", "flash", "entreprise", "memoire", "donnees", "controleur"),
    ),
    _CapabilityProfile(
        "solid state or magnetic data storage device",
        (
            "ssd",
            "disque dur",
            "hard drive",
            "nvme",
            "support de stockage",
            "solid state drive",
            "unite de memoire",
        ),
        ("stocker", "donnees", "serveur", "memoire", "pcie", "sas", "sata", "u2"),
    ),
    _CapabilityProfile(
        "data processing accelerator or expansion card",
        (
            "carte acceleratrice",
            "accelerateur",
            "gpu pcie",
            "expansion card",
            "carte pcie",
            "pcie card",
        ),
        (
            "calcul",
            "traitement",
            "hpc",
            "analyse de donnees",
            "intelligence artificielle",
            "serveur",
            "gpu",
            "inference",
            "training",
        ),
    ),
    _CapabilityProfile(
        "server automatic data processing machine",
        (
            "serveur informatique",
            "server computer",
            "serveur rack",
            "rack server",
            "compute server",
        ),
        ("traitement", "donnees", "processeur", "memoire", "rack", "enterprise"),
    ),
    _CapabilityProfile(
        "programmable industrial control equipment",
        ("plc", "automate programmable", "piloter des automatismes", "controleur industriel"),
        ("commande", "controle", "production", "sequence", "entrees", "sorties", "ethernet"),
    ),
    _CapabilityProfile(
        "static electrical power converter or variable speed drive",
        ("variateur", "convertisseur statique", "frequency drive", "inverter", "vfd"),
        ("moteur", "frequence", "puissance", "electrique", "tension"),
    ),
    _CapabilityProfile(
        "industrial robot",
        ("robot industriel", "operations robotisees", "bras robotise"),
        ("manutention", "production", "axes", "soudage", "assemblage"),
    ),
    _CapabilityProfile(
        "portable tablet or hybrid data processing computer",
        (
            "tablette",
            "pc hybride",
            "ordinateur portable tactile",
            "detachable tablet",
            "tablet computer",
        ),
        (
            "applications",
            "traitement",
            "donnees",
            "clavier",
            "ecran",
            "portable",
            "stylet",
            "tactile",
        ),
        ("telephone intelligent", "smartphone"),
    ),
    _CapabilityProfile(
        "rugged mobile data collection terminal",
        ("terminal mobile", "terminal durci", "ordinateur de poche", "data terminal"),
        ("scanner", "saisir", "donnees", "logistique", "entrepot", "code barres"),
    ),
    _CapabilityProfile(
        "mixed reality display headset",
        (
            "realite mixte",
            "realite virtuelle",
            "casque avec affichage",
            "display headset",
            "spatial computing",
            "head mounted display",
        ),
        ("afficher", "applications", "immersif", "portable", "optique", "micro oled", "vision"),
    ),
    _CapabilityProfile(
        "unmanned aircraft or drone",
        ("drone", "aeronef sans pilote"),
        ("vol", "aerien", "telecommande", "camera embarquee"),
    ),
)


def infer_technical_nature(
    designation: str,
    primary_function: str,
    characteristics: str,
    composition: str = "",
) -> TechnicalNature:
    """Infer a generic technical type without producing any customs code."""
    normalized = _normalize(
        " ".join([designation, primary_function, characteristics, composition])
    )
    if not normalized:
        return TechnicalNature("unspecified product", 0, ())

    best: tuple[float, _CapabilityProfile, tuple[str, ...]] | None = None
    for profile in _CAPABILITY_PROFILES:
        if any(term in normalized for term in profile.excluded):
            continue
        primary = tuple(term for term in profile.required_any if term in normalized)
        if not primary:
            continue
        supporting = tuple(term for term in profile.supporting if term in normalized)
        score = 3.0 * len(primary) + min(len(supporting), 5)
        signals = tuple(dict.fromkeys(primary + supporting))
        if best is None or score > best[0]:
            best = (score, profile, signals)

    if best is None:
        return TechnicalNature("unspecified product", 20, ())

    _, profile, signals = best
    confidence = min(95, 60 + 7 * min(len(signals), 5))
    return TechnicalNature(profile.name, confidence, signals)
