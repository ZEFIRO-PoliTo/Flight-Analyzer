"""Controlla che ogni testo da tradurre abbia la sua traduzione inglese.

Estrae con l'AST tutte le chiamate ``_("…")`` e ``N_("…")`` nei moduli di
flight_analyzer e le confronta con il catalogo ``i18n_en.EN``:

* testi senza traduzione (errore);
* traduzioni che non usano gli stessi segnaposto {nome} del testo italiano (errore);
* voci del catalogo che nessuno usa più (avviso).

Uso: python tests/check_i18n.py [--elenco]  (--elenco stampa i testi mancanti come voci da copiare)
"""

from __future__ import annotations

import ast
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flight_analyzer.i18n_en import EN  # noqa: E402

PKG = ROOT / "flight_analyzer"


def extract():
    found = {}
    for path in sorted(PKG.glob("*.py")):
        if path.name == "i18n_en.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("_", "N_")
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, []).append(f"{path.name}:{node.lineno}")
    return found


def fields(text):
    out = set()
    try:
        for _lit, name, _spec, _conv in string.Formatter().parse(text):
            if name is not None:
                out.add(name)
    except ValueError:
        pass
    return out


def shadowing():
    """Assegnazioni a ``_`` nei moduli che importano la funzione di traduzione.

    In Python un nome assegnato dentro una funzione è locale in tutta la funzione: un ``a, _, b = …``
    rende ``_("…")`` un errore (UnboundLocalError / 'str' object is not callable). Le comprehension
    hanno uno scope proprio e non danno problemi.
    """
    out = []
    for path in sorted(PKG.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(isinstance(n, ast.ImportFrom) and any(a.name == "_" for a in n.names) for n in ast.walk(tree)):
            continue

        class Visitor(ast.NodeVisitor):
            def visit_ListComp(self, node):
                pass

            visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_ListComp

            def visit_Name(self, node):
                if node.id == "_" and isinstance(node.ctx, (ast.Store, ast.Del)):
                    out.append(f"{path.name}:{node.lineno}")

            def visit_arg(self, node):
                if node.arg == "_":
                    out.append(f"{path.name}:{node.lineno}")

        Visitor().visit(tree)
    return out


def main():
    shadow = shadowing()
    for loc in shadow:
        print(f"  OMBRA  {loc}: assegnazione a '_' in un modulo che usa _() per tradurre")
    found = extract()
    missing = [t for t in found if t not in EN]
    bad_fields = [t for t in found if t in EN and fields(t) != fields(EN[t])]
    unused = [t for t in EN if t not in found]
    # parole italiane rimaste nella traduzione (controllo grossolano)
    italian = re.compile(r"\b(della|degli|delle|non è|anello chiuso|velocità|assetto|rollio|beccheggio|imbardata)\b",
                         re.IGNORECASE)
    suspicious = [t for t in found if t in EN and italian.search(EN[t])]
    print(f"Testi da tradurre: {len(found)}; tradotti: {len(found) - len(missing)}")
    for t in missing:
        print(f"  MANCA  {found[t][0]}: {t!r}")
    for t in bad_fields:
        print(f"  SEGNAPOSTO  {found[t][0]}: {sorted(fields(t))} ≠ {sorted(fields(EN[t]))}: {t!r}")
    for t in suspicious:
        print(f"  ITALIANO?  {found[t][0]}: {EN[t]!r}")
    for t in unused:
        print(f"  (non usato) {t!r}")
    if "--elenco" in sys.argv:
        for t in missing:
            print(f"    {t!r}: {t!r},")
    ok = not missing and not bad_fields and not shadow
    print("OK" if ok else "ERRORI")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
