# KATALOG CÍLŮ

Tvary cílových prostředí a jejich rozpočty. Čti při volbě cíle (§1) a před
kompilací.

**Čísla jsou orientační.** Platformy limity mění bez ohlášení. Zná-li uživatel
skutečný limit svého prostředí, jeho číslo přebíjí tabulku — předej ho
kompilátoru přes `--budget`.

---

## Tvary

Kompilátor umí dva tvary. Tvar je důležitější než konkrétní platforma — nová
platforma zpravidla zapadne do jednoho z nich.

### `single` — jedno vstupní pole

Všechno v jednom bloku: role, tiery, věta o prioritách. Nejběžnější tvar.

### `dual` — dvě vstupní pole

`POLE A` nese stabilní kontext a technický profil, `POLE B` chování (tiery).
Rozpočet se počítá pro každé pole zvlášť — přeteče-li jedno, kompilátor krátí
jen jeho obsah.

Rozdělení není libovolné: pole A odpovídá „co o mně máš vědět", pole B „jak se
máš chovat". Když se profil vejde do A, zůstane v B víc místa na operační
pravidla, a ta jsou to, co reálně mění chování.

---

## Rozpočty

| Cíl | Tvar | Rozpočet | Poznámka |
|---|---|---|---|
| Dvoupolové custom instructions | `dual` | 2 × ~1400 znaků | A = kontext, B = chování |
| Jednopolové krátké (styly, persony) | `single` | 800–1500 znaků | jen TIER 0–1 + 3–5 DEFAULTS |
| Jednopolové střední (projekty, asistenti) | `single` | 3000–6000 znaků | plná struktura |
| Systémový prompt přes API | `single` | 3000–8000 znaků | plná struktura + explicitní priority |
| Malý model (≤13B) nebo edge | `single` | 600–1200 znaků | KERNEL MODE podle §12 |
| Neznámý cíl | `single` | 2000 znaků | označ v hlavičce jako odhad |

---

## Volba cíle, když je uživatel vágní

Řekne-li jen „udělej mi instrukce", zeptej se jednou větou a nabídni volby.
Neptej se na rozpočet zvlášť — ten plyne z cíle.

Signály, které cíl prozradí bez ptaní:

| Signál v zadání | Pravděpodobný cíl |
|---|---|
| „custom instructions", „dvě pole" | `dual`, 2 × 1400 |
| „projekt", „asistent", „Gem", „GPT" | `single`, 3000–6000 |
| „přes API", „system prompt v kódu" | `single`, 3000–8000 |
| „lokálně", „Ollama", „7B", „na Raspberry" | `single`, 600–1200, KERNEL |
| „styl", „persona", „krátké" | `single`, 800–1500 |

Rozpoznáš-li cíl z kontextu spolehlivě, potvrď ho jednou větou a pokračuj —
potvrzovací otázka je levnější než otevřená.

---

## Poznámka k lokálním modelům

U cílů pod 1200 znaků nejde jen o délku. Slabší model složitá pravidla nedodrží
a zahodí je jako celek, takže KERNEL MODE (§12) není jen krácení — je to jiná
gramatika pravidel: krátké imperativy, žádné zanořování, žádné podmínkové
řetězce.

Prakticky to znamená: v KERNEL MODE raději obětuj TRIGGERY (podmíněná pravidla)
a nech INVARIANTY a DEFAULTY. Podmínka, kterou model nevyhodnotí správně, je
horší než pravidlo, které tam není.
