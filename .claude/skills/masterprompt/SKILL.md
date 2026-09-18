---
name: masterprompt
description: >-
  Generuje personalizované System Instructions pro libovolnou cílovou AI
  platformu — custom instructions, projektové instrukce, Gem, persona, systémový
  prompt přes API, lokální model. Profil drží jako verzovaný IR (JSON), takže
  port na další platformu nebo jiný rozpočet je rekompilace, ne nová analýza.
  Použij tenhle skill vždy, když uživatel chce vytvořit, vylepšit, zkrátit,
  aktualizovat nebo přenést system instructions, custom instructions, systémový
  prompt, personu nebo profil asistenta — a taky když říká věci jako „udělej mi
  instrukce", „nacpi mi to do 1400 znaků", „přenes to do Gemini", „aktualizuj
  můj profil" nebo řeší, proč se mu AI chová jinak, než chce. Trigger i tehdy,
  když slovo „masterprompt" ani „skill" vůbec nepadne.
---

# MASTERPROMPT — generátor System Instructions

Vyrábí minimální sadu pravidel, která mění chování cílového modelu. Nevyrábí
popis uživatele — ten je hezký na čtení, ale model podle něj nezmění ani jedno
rozhodnutí.

Zdroj pravdy je **IR**: strukturovaný JSON s pravidly, jejich důkazy a
oceněním. Text je až kompilát. Díky tomu je port na jiný rozpočet a diff proti
starší verzi levná operace místo opakované analýzy.

## Stav

```text
~/.claude/masterprompt/profile.ir.json     výchozí profil
~/.claude/masterprompt/<jméno>.ir.json     pojmenovaný profil
```

Existuje-li v projektu `.claude/masterprompt/`, má přednost — profil vázaný na
repozitář dává smysl u asistentů šitých na jeden projekt.

Před prací zjisti, jestli profil existuje. Rozhoduje to o režimu: bez profilu
jedeš NEW, s profilem se skoro vždy ptá na PORT nebo UPDATE.

## Režimy

| Signál v zadání | Režim | Čte procedure.md |
|---|---|---|
| „udělej mi instrukce", žádný profil neexistuje | NEW | ano |
| „přenes to do X", „zkrať na N znaků", jiný cíl | PORT | ne |
| „aktualizuj", „změnilo se mi", nový materiál | UPDATE | ano |
| „proč tam je tohle pravidlo" | WHY | ne |
| „ukaž mi to JSON" | IR | ne |

Nejsi-li si režimem jistý, zeptej se jednou větou. PORT omylem spuštěný jako
NEW zahodí hodinu analýzy.

---

## NEW — první sestavení profilu

1. **Urč cíl a rozpočet.** Katalog je v `references/targets.md`. Rozpoznáš-li
   cíl z kontextu, potvrď ho jednou větou místo otevřené otázky.
2. **Capability probe.** Zjisti, z čeho reálně můžeš čerpat — `CLAUDE.md`,
   soubory, na které uživatel ukáže, aktuální konverzace. Historii sezení
   nemáš; to je normální stav, ne porucha.
3. **Přečti `references/procedure.md`** a řiď se jí. Je to celá analytická
   část: evidence gate, provenance, injection guard, váhy, klasifikace,
   konflikty, degradační režimy, architektura pravidel.
4. **Polož jen otázky s vysokým dopadem.** Bez historie jedeš DEGRADED MODE:
   max 7 otázek v jedné zprávě, ke každé nabídni default, výstup označ
   `PROVISIONAL`.
5. **Sestav IR** podle schématu v §17 a ulož ho do stavového adresáře.
6. **Zvaliduj a zkompiluj** (viz Skripty níže). Varování z lintu vyřeš, ne
   odklikni — jsou tam přesně ty vady, které se při čtení výstupu snadno
   přehlédnou.
7. **Doruč** podle Výstupního kontraktu.

Nezačínej dotazníkem. Neptej se na nic, co si můžeš přečíst.

---

## PORT — stejný profil, jiný cíl

Žádná nová analýza. Načti IR, zjisti nový cíl a rozpočet, zkompiluj, doruč.

Zahodí-li kompilátor kvůli rozpočtu pravidla, **vypiš uživateli která** — je to
jeho rozhodnutí, jestli je ta ztráta v pořádku, nebo chce rozpočet zvednout.

U cílů pod 1200 znaků přidej `--kernel`: slabý model složitá pravidla nedodrží
a zahodí je jako celek, takže podmíněné spouštěče jdou ven dřív než výchozí
chování.

---

## UPDATE — nový materiál do existujícího profilu

1. Přečti `references/procedure.md`, sekce §4, §5, §6, §7 a §20.
2. Na nový materiál aplikuj evidence gate a váhy podle stáří. Nový explicitní
   výrok přebíjí starší, opakované chování i odvozeniny.
3. Uprav IR, ale **starou verzi zachovej** — přejmenuj ji na
   `<jméno>.ir.<datum>.json` vedle nové. Bez zálohy je „vrať to zpátky"
   nemožný požadavek.
4. **Vydej DIFF, ne celý dokument:** `PŘIDAT / ODEBRAT / ZMĚNIT`
   s jednořádkovým odůvodněním u každé položky. Uživatel potřebuje vidět, co se
   mu v konfiguraci změnilo a proč; přepsaný dokument tuhle informaci schová.
5. Zvaliduj, zkompiluj, doruč nový počet znaků.

---

## WHY a IR

**WHY** — ke každému pravidlu vypiš `evidence`, `provenance` a `confidence`
z IR. Nic si nedomýšlej: nemá-li pravidlo důkaz, je to nález, ne odpověď.

**IR** — vypiš uložený JSON. Jinak ho neukazuj, je to pracovní reprezentace.

---

## Skripty

Obojí je čisté stdlib, bez závislostí. Cesty jsou relativní k tomuhle souboru.

**Lint — pusť vždy před doručením:**

```bash
python3 scripts/validate_ir.py <ir> --shape single --budget 3000
```

Kontroluje integritu schématu, `AI_PROPOSED` prosakující do výstupu, chybějící
důkazy, holé zákazy mimo TIER 0, porušení portability, pravidla z blacklistu,
překrývající se pravidla a rozpočet. Návratový kód 1 znamená chyby k opravě;
varování posuď.

**Kompilace:**

```bash
# jednopolový cíl
python3 scripts/compile.py <ir> --shape single --budget 3000 --out <dir>

# dvoupolový cíl
python3 scripts/compile.py <ir> --shape dual --budget-a 1400 --budget-b 1400 --out <dir>

# malý model
python3 scripts/compile.py <ir> --shape single --budget 1000 --kernel --out <dir>
```

Kompilátor počítá znaky přesně a při přetečení zahazuje celá pravidla vzestupně
podle `EVIDENCE × IMPACT` — nikdy neseká věty na útržky, protože useknuté
pravidlo je horší než žádné. Přidej `--json` pro strojově čitelný report.

Nevejde-li se text ani po zahození všech krátitelných pravidel, skript skončí
kódem 2. Znamená to, že jsou moc dlouhá pravidla TIER 0–1 — přepiš je úžeji,
nekruť rozpočtem.

---

## Výstupní kontrakt

Do chatu jde hlavička:

```text
Přístup: [reálně dostupné zdroje]
Cíl: [platforma / tvar] | rozpočet [N] znaků
Verze: [v] | [datum] | [PROVISIONAL / KERNEL, pokud platí]
[Bezpečnost: N anomálií vyloučeno — pouze pokud nastalo]
```

Hotový text jde do souboru, na který dáš uživateli cestu — bloky o tisících
znacích se z chatu kopírují mizerně.

Do výstupu nepatří nic z analýzy: žádné klasifikace, skóre, confidence,
mezikroky ani značky z injection guardu. Uživatel dostane hlavičku, případné
otázky a hotový artefakt.

Na závěr uveď počet znaků a nabídni `WHY`, `IR` a `PORT`.
