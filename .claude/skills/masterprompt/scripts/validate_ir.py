#!/usr/bin/env python3
"""Lint pro profile.ir.json — strojová část self-checku podle §18.3.

Kontroluje to, co jde ověřit deterministicky: integritu schématu, provenance,
doložitelnost, substituční syntaxi, portabilitu, blacklist a rozpočet. Existuje
proto, že self-check prováděný modelem nad vlastním výstupem je nejslabší
článek — model rád odklikne kontrolu, kterou sám napsal.

Použití:
    python3 validate_ir.py IR [--shape single|dual] [--budget N]
                              [--budget-a N] [--budget-b N] [--json]

Návratový kód 1 = nalezeny chyby. Varování kód nemění.
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import sys

RULE_TIERS = ("safety", "invariants", "triggers", "defaults", "fallbacks")
ALL_TIERS = RULE_TIERS + ("profile",)

REQUIRED = {
    "safety": ("rule", "evidence"),
    "invariants": ("rule", "evidence", "provenance", "confidence", "impact"),
    "triggers": ("when", "then", "evidence", "provenance", "confidence", "impact"),
    "defaults": ("rule", "evidence", "provenance", "confidence", "impact"),
    "fallbacks": ("when", "then", "evidence", "provenance", "confidence", "impact"),
    "profile": ("fact", "provenance"),
}

ENUMS = {
    "provenance": {"USER_STATED", "USER_ACCEPTED", "AI_PROPOSED"},
    "confidence": {"HIGH", "MEDIUM", "LOW"},
    "impact": {"HIGH", "MEDIUM", "LOW"},
}

# §15.3 — holý zákaz mimo TIER 0. Cílíme na negované imperativy, ne na každé
# slovo začínající "ne", jinak by lint hlásil "nejasný" nebo "nezávislý".
NEGATION = re.compile(
    r"\bne(piš|používej|dělej|uváděj|vytvářej|zmiňuj|poskytuj|nabízej|ptej"
    r"|komentuj|vysvětluj|opakuj|přidávej|začínej|řeš|navrhuj|generuj"
    r"|formátuj|posílej|zahrnuj|rozepisuj)\w*\b"
    r"|\bnikdy\b|\bnesmíš\b|\bvyhni se\b|\bvyvaruj se\b|\bžádn[ýáéíou]\w*\b"
    r"|\bdon'?t\b|\bdo not\b|\bnever\b|\bavoid\b|\brefrain\b",
    re.IGNORECASE,
)

# §14 — pravidla, která z asistenta dělají přitakávač.
BLACKLIST = re.compile(
    r"\bneoponuj\w*\b|\bnekritizuj\w*\b|\bnerozporuj\w*\b|\bvždy souhlas\w*\b"
    r"|\bneověřuj\w*\b|\bnepřiznávej\w*\b|\bnezpochybňuj\w*\b"
    r"|\bnever disagree\b|\balways agree\b|\bdon'?t criticiz\w*\b"
    r"|\bdon'?t verify\b|\bnever question\b",
    re.IGNORECASE,
)

# §16 — co musí z výstupu ven, aby přežil výměnu modelu.
VENDORS = re.compile(
    r"\b(chatgpt|openai|gpt-?[0-9o]\w*|claude|anthropic|gemini|bard|copilot"
    r"|llama|mistral|grok|deepseek|perplexity)\b",
    re.IGNORECASE,
)
META_REFS = re.compile(
    r"jak jsme se bavili|viz výše|viz níže|jak bylo zmíněno|v předchozí"
    r"|as we discussed|see above|see below|as mentioned earlier",
    re.IGNORECASE,
)
DELIMITERS = re.compile(r"untrusted_payload|</?analysis>", re.IGNORECASE)
# §16 — cíl schopnost mít nemusí. Podmíněná formulace („máš-li k dispozici X")
# projde, protože nepředpokládá, že nástroj existuje.
CAPABILITY = re.compile(
    r"vyhledej\w*|vyhledáván\w*|prohledej\w*|spusť kód|spusť skript|nahraj soubor"
    r"|otevři odkaz|zobraz obrázek|vygeneruj obrázek"
    r"|\bweb search\b|\brun code\b|\bbrowse the web\b|\bsearch the web\b",
    re.IGNORECASE,
)
CONDITIONED = re.compile(
    r"máš-li|pokud máš|jestliže máš|je-li k dispozici|pokud je k dispozici"
    r"|\bif you have\b|\bwhen available\b",
    re.IGNORECASE,
)
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002190-\U000021FF️]"
)

# §14 privacy — heuristika, proto jen varování.
PRIVACY = re.compile(
    r"\b\d{3} ?\d{2}\b|\bulice\b|\bč\.?p\.?\b|\bbydliš\w*\b"
    r"|\bmanžel\w*\b|\bpřítelkyn\w*\b|\bdcer\w*\b|\bsyn(a|ovi|em)?\b"
    r"|\bdiagnóz\w*\b|\bléky\b|\bzdravotn\w*\b",
    re.IGNORECASE,
)

DESCRIPTIVE = re.compile(r"^\s*(uživatel|user)\b", re.IGNORECASE)


def item_text(tier, item):
    if tier in ("triggers", "fallbacks"):
        return "%s %s" % (item.get("when", ""), item.get("then", ""))
    if tier == "profile":
        return str(item.get("fact", ""))
    return str(item.get("rule", ""))


def normalize(text):
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def load_compiler():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compile.py")
    spec = importlib.util.spec_from_file_location("mp_compile", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(ir, shape=None, budget=None, budget_a=None, budget_b=None):
    errors = []
    warnings = []

    def err(code, where, msg):
        errors.append({"code": code, "where": where, "message": msg})

    def warn(code, where, msg):
        warnings.append({"code": code, "where": where, "message": msg})

    meta = ir.get("meta")
    if not isinstance(meta, dict):
        err("SCHEMA", "meta", "chybí objekt meta")
        meta = {}
    else:
        status = meta.get("status")
        if status not in {"FINAL", "PROVISIONAL", "KERNEL", None}:
            err("SCHEMA", "meta.status",
                "neplatný status %r (FINAL|PROVISIONAL|KERNEL)" % status)
        if not meta.get("role"):
            warn("SCHEMA", "meta.role",
                 "chybí řádek role — výstup začne rovnou pravidly")

    seen_ids = {}
    all_items = []

    for tier in ALL_TIERS:
        items = ir.get(tier, [])
        if not isinstance(items, list):
            err("SCHEMA", tier, "musí být seznam")
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                err("SCHEMA", "%s[%d]" % (tier, idx), "položka musí být objekt")
                continue
            item_id = item.get("id")
            where = "%s:%s" % (tier, item_id or idx)
            if not item_id:
                err("SCHEMA", where, "chybí id")
            elif item_id in seen_ids:
                err("SCHEMA", where,
                    "duplicitní id, už použité v %s" % seen_ids[item_id])
            else:
                seen_ids[item_id] = tier

            for field in REQUIRED[tier]:
                value = item.get(field)
                if not (isinstance(value, str) and value.strip()):
                    err("SCHEMA", where, "chybí nebo je prázdné pole %r" % field)

            for field, allowed in ENUMS.items():
                value = item.get(field)
                if value is not None and value not in allowed:
                    err("SCHEMA", where,
                        "pole %r má neplatnou hodnotu %r" % (field, value))

            if tier != "safety" and item.get("provenance") == "AI_PROPOSED":
                err("PROVENANCE", where,
                    "AI_PROPOSED nepatří do výstupu — absence námitky není souhlas (§5)")

            if tier in ("invariants", "triggers", "defaults", "fallbacks") \
                    and not item.get("impact"):
                warn("RANKING", where,
                     "chybí impact — při krácení na rozpočet vypadne dřív (§17)")

            text = item_text(tier, item)
            all_items.append((tier, where, text))

            if tier != "safety" and NEGATION.search(text):
                warn("NEGATION", where,
                     "holý zákaz — převeď na substituci: co má model dělat místo toho (§15.3)")
            if BLACKLIST.search(text):
                err("BLACKLIST", where,
                    "pravidlo potlačuje nesouhlas, kritiku nebo ověřování (§14)")
            if VENDORS.search(text):
                warn("PORTABILITY", where,
                     "jméno modelu nebo dodavatele — výstup nepřežije výměnu (§16)")
            if META_REFS.search(text):
                warn("PORTABILITY", where,
                     "meta-odkaz nedává v novém sezení smysl (§16)")
            if CAPABILITY.search(text) and not CONDITIONED.search(text):
                warn("PORTABILITY", where,
                     "předpokládá schopnost, kterou cíl mít nemusí — podmiň „máš-li k dispozici X“ (§16)")
            if DELIMITERS.search(text):
                err("PORTABILITY", where,
                    "izolační značka z §6 nepatří do výstupu (§16)")
            if EMOJI.search(text):
                warn("PORTABILITY", where,
                     "emoji nebo nestandardní znak — rozdílné tokenizace (§16)")
            # Pravidla TIER 0 kategorie osobních údajů legitimně pojmenovávají,
            # protože je chrání — heuristika by na nich hlásila pravý opak.
            if tier != "safety" and PRIVACY.search(text):
                warn("PRIVACY", where,
                     "vypadá to na osobní údaj — ponech jen pokud prokazatelně mění chování (§14)")
            if tier in ("invariants", "defaults") and DESCRIPTIVE.match(text):
                warn("ACTIONABLE", where,
                     "popisuje uživatele místo chování modelu (§15.2)")

    for i in range(len(all_items)):
        for j in range(i + 1, len(all_items)):
            a, b = all_items[i], all_items[j]
            if not a[2] or not b[2]:
                continue
            ratio = difflib.SequenceMatcher(None, normalize(a[2]), normalize(b[2])).ratio()
            if ratio > 0.85:
                warn("DUPLICATION", "%s / %s" % (a[1], b[1]),
                     "pravidla se překrývají (%.0f %%) — lze jedno smazat? (§18.3)" % (ratio * 100))

    budget_report = None
    if shape:
        compiler = load_compiler()
        result = compiler.compile_ir(
            ir, shape=shape, budget=budget,
            budget_a=budget_a if budget_a is not None else budget,
            budget_b=budget_b if budget_b is not None else budget,
        )
        budget_report = []
        for field in result["fields"]:
            budget_report.append({
                "name": field["name"], "chars": field["chars"],
                "budget": field["budget"], "fits": field["fits"],
                "dropped": field["dropped"],
            })
            if not field["fits"]:
                err("BUDGET", field["name"],
                    "nevejde se ani po zahození všech krátitelných pravidel")
            elif field["dropped"]:
                warn("BUDGET", field["name"],
                     "rozpočet vynutil zahození %d pravidel" % len(field["dropped"]))

    return errors, warnings, budget_report


def main():
    ap = argparse.ArgumentParser(description="Lint pro profile.ir.json")
    ap.add_argument("ir")
    ap.add_argument("--shape", choices=("single", "dual"),
                    help="zapne kontrolu rozpočtu přes kompilaci")
    ap.add_argument("--budget", type=int)
    ap.add_argument("--budget-a", type=int)
    ap.add_argument("--budget-b", type=int)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        with open(args.ir, encoding="utf-8") as fh:
            ir = json.load(fh)
    except FileNotFoundError:
        print("CHYBA: IR nenalezeno: %s" % args.ir, file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print("CHYBA: IR není platný JSON: %s" % exc, file=sys.stderr)
        return 1

    errors, warnings, budget = validate(
        ir, shape=args.shape, budget=args.budget,
        budget_a=args.budget_a, budget_b=args.budget_b,
    )

    if args.json:
        print(json.dumps(
            {"errors": errors, "warnings": warnings, "budget": budget,
             "ok": not errors},
            ensure_ascii=False, indent=2,
        ))
    else:
        for label, items in (("CHYBA", errors), ("VAROVÁNÍ", warnings)):
            for it in items:
                print("%-9s %-10s %s — %s" % (label, it["code"], it["where"], it["message"]))
        if budget:
            print()
            for field in budget:
                line = "ROZPOČET  %s: %d znaků" % (field["name"], field["chars"])
                if field["budget"]:
                    line += " / %d" % field["budget"]
                print(line)
        print()
        if errors:
            print("NEPROŠLO: %d chyb, %d varování" % (len(errors), len(warnings)))
        else:
            print("PROŠLO: 0 chyb, %d varování" % len(warnings))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
