"""Traduzione dell'interfaccia (italiano, lingua di partenza, e inglese).

Uso:
    from .i18n import _, N_
    label = _("Rollio")                     # tradotto al momento dell'uso
    LABELS = {"roll": N_("Rollio")}         # solo marcato: si traduce con _() quando si mostra

Le stringhe con valori variabili si scrivono con segnaposto e .format():
    _("Solo {t:.1f} s di volo utile").format(t=total)

Il catalogo inglese è in i18n_en.py; tests/check_i18n.py controlla che ogni
stringa marcata con _() o N_() abbia la sua traduzione.
"""

from __future__ import annotations

SUPPORTED = {"it": "Italiano", "en": "English"}
_LANG = "it"
_CATALOG: dict | None = None


def set_language(code: str):
    global _LANG
    _LANG = code if code in SUPPORTED else "it"


def language() -> str:
    return _LANG


def _load():
    global _CATALOG
    if _CATALOG is None:
        from .i18n_en import EN

        _CATALOG = EN
    return _CATALOG


def _(text: str) -> str:
    """Traduce ``text`` nella lingua attiva (l'italiano è la lingua di partenza)."""
    if _LANG == "it" or not text:
        return text
    return _load().get(text, text)


def N_(text: str) -> str:
    """Marca una stringa da tradurre più tardi (costanti a livello di modulo)."""
    return text


def num(value, decimals=1) -> str:
    """Numero con il separatore decimale della lingua (virgola in italiano)."""
    txt = f"{value:.{decimals}f}"
    return txt.replace(".", ",") if _LANG == "it" else txt
