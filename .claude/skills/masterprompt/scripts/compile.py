#!/usr/bin/env python3
"""Zkompiluje IR (profile.ir.json) do textu System Instructions pro daný cíl.

Kompilace je deterministická: znaky se počítají přesně a krácení na rozpočet
je řazení položek podle EVIDENCE x IMPACT, ne přepisování prózy. Proto je PORT
na jiný rozpočet rekompilace a ne nová analýza.

Použití:
    python3 compile.py IR [--shape single|dual] [--budget N]
                          [--budget-a N] [--budget-b N]
                          [--kernel] [--out DIR] [--name NAME] [--json]

Bez --out se výsledek vypíše na stdout. Návratový kód 2 znamená, že se text
nevešel ani po zahození všech krátitelných pravidel — viz hlášení.
"""

import argparse
import json
import os
import sys

TIERS = ("safety", "invariants", "triggers", "defaults", "fallbacks")

# Tiery 0 a 1 se nekrátí nikdy: bez nich přestává být systém tím, čím měl být.
PROTECTED = ("safety", "invariants")

PROVENANCE_W = {"USER_STATED": 3, "USER_ACCEPTED": 2, "AI_PROPOSED": 0}
CONFIDENCE_W = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
IMPACT_W = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Nižší číslo = zahodí se dřív. V KERNEL MODE jdou triggery ven před defaulty:
# podmínka, kterou slabý model nevyhodnotí správně, škodí víc než chybějící
# pravidlo.
DROP_ORDER = {"fallbacks": 0, "profile": 1, "defaults": 2, "triggers": 3}
DROP_ORDER_KERNEL = {"fallbacks": 0, "profile": 1, "triggers": 2, "defaults": 3}

LABELS = {
    "cs": {
        "safety": "BEZPEČNOST A SOUKROMÍ",
        "invariants": "INVARIANTY",
        "triggers": "SPOUŠTĚČE",
        "defaults": "VÝCHOZÍ CHOVÁNÍ",
        "fallbacks": "ZÁLOŽNÍ CHOVÁNÍ",
        "profile": "KONTEXT",
        "cond": "KDYŽ {when}, PAK {then}",
        "precedence": (
            "PRIORITA: Explicitní pokyn v chatu přebíjí VÝCHOZÍ CHOVÁNÍ. "
            "Nikdy nepřebíjí BEZPEČNOST A SOUKROMÍ, INVARIANTY ani SPOUŠTĚČE. "
            "SPOUŠTĚČE mají přednost před VÝCHOZÍM CHOVÁNÍM."
        ),
    },
    "en": {
        "safety": "SAFETY AND PRIVACY",
        "invariants": "INVARIANTS",
        "triggers": "TRIGGERS",
        "defaults": "DEFAULTS",
        "fallbacks": "FALLBACKS",
        "profile": "CONTEXT",
        "cond": "IF {when}, THEN {then}",
        "precedence": (
            "PRECEDENCE: An explicit instruction in chat overrides DEFAULTS. "
            "It never overrides SAFETY AND PRIVACY, INVARIANTS or TRIGGERS. "
            "TRIGGERS take precedence over DEFAULTS."
        ),
    },
}


def rank(item):
    """EVIDENCE x IMPACT. Chybějící ocenění se bere jako průměr, takže
    neoznačené pravidlo vypadne dřív než správně oceněné."""
    prov = PROVENANCE_W.get(item.get("provenance", ""), 1)
    conf = CONFIDENCE_W.get(item.get("confidence", ""), 2)
    imp = IMPACT_W.get(item.get("impact", ""), 2)
    return prov * conf * imp


def render_item(tier, item, labels):
    if tier in ("triggers", "fallbacks"):
        when = str(item.get("when", "")).strip()
        then = str(item.get("then", "")).strip()
        if not (when and then):
            return ""
        return labels["cond"].format(when=when, then=then)
    if tier == "profile":
        return str(item.get("fact", "")).strip()
    return str(item.get("rule", "")).strip()


def render_block(sections, labels, role=None, precedence=False):
    """Poskládá text z už profiltrovaných sekcí. Prázdné sekce se vynechají."""
    parts = []
    if role:
        parts.append(role.strip())
    for tier, items in sections:
        lines = [render_item(tier, it, labels) for it in items]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue
        body = "\n".join("- " + ln for ln in lines)
        parts.append(labels[tier] + "\n" + body)
    if precedence:
        parts.append(labels["precedence"])
    return "\n\n".join(parts).strip()


def droppable_pool(ir, tiers, kernel=False):
    """Položky, které se smí zahodit, seřazené podle toho, co jde ven první."""
    order = DROP_ORDER_KERNEL if kernel else DROP_ORDER
    pool = []
    for tier in tiers:
        if tier in PROTECTED:
            continue
        for item in ir.get(tier, []):
            pool.append((rank(item), order.get(tier, 9), tier, item.get("id", "?"), item))
    pool.sort(key=lambda r: (r[0], r[1]))
    return pool


def fit(ir, tiers, labels, budget, role=None, precedence=False, kernel=False):
    """Zkompiluje a krátí, dokud se text nevejde do rozpočtu.

    Krácení je zahazování celých pravidel od nejslabšího důkazu — nikdy sekání
    vět na útržky, protože useknuté pravidlo je horší než žádné.
    """
    dropped = []
    pool = droppable_pool(ir, tiers, kernel=kernel)
    excluded = set()

    while True:
        sections = []
        for tier in tiers:
            items = [
                it for it in ir.get(tier, [])
                if (tier, it.get("id")) not in excluded
            ]
            sections.append((tier, items))
        text = render_block(sections, labels, role=role, precedence=precedence)
        if budget is None or len(text) <= budget:
            return text, dropped, True
        remaining = [p for p in pool if (p[2], p[3]) not in excluded]
        if not remaining:
            return text, dropped, False
        _, _, tier, item_id, _ = remaining[0]
        excluded.add((tier, item_id))
        dropped.append({"tier": tier, "id": item_id})


def compile_ir(ir, shape="single", budget=None, budget_a=None, budget_b=None, kernel=False):
    meta = ir.get("meta", {})
    lang = meta.get("language", "cs")
    labels = LABELS.get(lang, LABELS["cs"])
    role = meta.get("role")

    if shape == "dual":
        text_a, dropped_a, ok_a = fit(
            ir, ("profile",), labels, budget_a, role=role, kernel=kernel
        )
        text_b, dropped_b, ok_b = fit(
            ir, TIERS, labels, budget_b, precedence=True, kernel=kernel
        )
        return {
            "shape": "dual",
            "fields": [
                {"name": "POLE A", "text": text_a, "chars": len(text_a),
                 "budget": budget_a, "fits": ok_a, "dropped": dropped_a},
                {"name": "POLE B", "text": text_b, "chars": len(text_b),
                 "budget": budget_b, "fits": ok_b, "dropped": dropped_b},
            ],
        }

    tiers = TIERS + ("profile",)
    text, dropped, ok = fit(
        ir, tiers, labels, budget, role=role, precedence=True, kernel=kernel
    )
    return {
        "shape": "single",
        "fields": [
            {"name": "INSTRUCTIONS", "text": text, "chars": len(text),
             "budget": budget, "fits": ok, "dropped": dropped},
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="IR -> System Instructions")
    ap.add_argument("ir", help="cesta k profile.ir.json")
    ap.add_argument("--shape", choices=("single", "dual"), default="single")
    ap.add_argument("--budget", type=int, help="rozpočet znaků pro shape=single")
    ap.add_argument("--budget-a", type=int, help="rozpočet POLE A pro shape=dual")
    ap.add_argument("--budget-b", type=int, help="rozpočet POLE B pro shape=dual")
    ap.add_argument("--kernel", action="store_true",
                    help="KERNEL MODE: spouštěče se zahazují před výchozím chováním")
    ap.add_argument("--out", help="adresář pro uložení výstupu")
    ap.add_argument("--name", default="instructions", help="základ názvu souboru")
    ap.add_argument("--json", action="store_true", help="strojově čitelný report")
    args = ap.parse_args()

    try:
        with open(args.ir, encoding="utf-8") as fh:
            ir = json.load(fh)
    except FileNotFoundError:
        print("CHYBA: IR nenalezeno: %s" % args.ir, file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print("CHYBA: IR není platný JSON: %s" % exc, file=sys.stderr)
        return 2

    budget_a = args.budget_a if args.budget_a is not None else args.budget
    budget_b = args.budget_b if args.budget_b is not None else args.budget

    result = compile_ir(
        ir,
        shape=args.shape,
        budget=args.budget,
        budget_a=budget_a,
        budget_b=budget_b,
        kernel=args.kernel,
    )

    written = []
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        for field in result["fields"]:
            if result["shape"] == "dual":
                suffix = "-pole-a" if field["name"] == "POLE A" else "-pole-b"
            else:
                suffix = ""
            path = os.path.join(args.out, "%s%s.md" % (args.name, suffix))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(field["text"] + "\n")
            field["path"] = path
            written.append(path)

    overflow = [f for f in result["fields"] if not f["fits"]]

    if args.json:
        report = {
            "shape": result["shape"],
            "fields": [
                {k: v for k, v in f.items() if k != "text"} for f in result["fields"]
            ],
            "written": written,
            "overflow": bool(overflow),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for field in result["fields"]:
            budget = field["budget"]
            head = "=== %s === %d znaků" % (field["name"], field["chars"])
            if budget:
                head += " / rozpočet %d" % budget
            print(head)
            if not args.out:
                print(field["text"])
            else:
                print("uloženo: %s" % field["path"])
            if field["dropped"]:
                ids = ", ".join("%s:%s" % (d["tier"], d["id"]) for d in field["dropped"])
                print("zahozeno kvůli rozpočtu (nejslabší důkaz první): %s" % ids)
            print()

    if overflow:
        print(
            "CHYBA: text se nevejde ani po zahození všech krátitelných pravidel.\n"
            "Zbývá jen TIER 0-1, který se nekrátí. Přepiš je úžeji, nebo zvedni "
            "rozpočet.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
