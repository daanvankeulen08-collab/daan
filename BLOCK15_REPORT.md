# BLOCK 1.5 — LFM3-1.7B CAPABILITY RESEARCH

**Status:** RONDE 1 UITGEVOERD EN GELOGD  
**Datum:** 2026-11-10  
**Model:** `lfm3:latest`  
**Modeldigest:** `b36a103fe2f8fbe9df2ceec88b9cfdf842dc04aaabe2b4677d1acf8e16570b5d`  
**Stopcriterium:** nagekomen — geen training gestart, Block 1 niet gewijzigd, geen Block 2 gebouwd, niets gedownload.

---

## 0. Method, infrastructuur en compliantie

### Wat werd gebruikt
De benchmark gebruikt uitsluitend bestaande componenten:

- `mdl.OllamaClient` — single-flight LFM3-inferentie, harde time-outs.
- `mdl.ToolOrchestrator` + `mdl.expr_parser` — allowlisted `symbolic_expand`.
- `mdl.verifier` — onafhankelijke SymPy-verificatie van tooluitkomsten.
- `mdl.ResearchStore` — SQLite + append-only hash-chained JSONL.
- `mdl.config.Settings` — contextlimiet 8192, single-flight, minimale time-outs.
- Nieuw Block 1.5-pakket `block15/` voegt alleen taken, runner en checks toe; het wijzigt geen Block 1-module.

### Modelinstellingen
- `think=false`
- `num_ctx=8192`
- `temperature=0.1`
- `top_p=1.0`
- `repeat_penalty=1.1`
- `seed=42`
- `keep_alive=10m`
- Single-flight; alle calls sequentieel.
- Outputbudget: `num_predict=300` voor toolbeslissing, `num_predict=1200` voor eindantwoorden.

### Data en bewijs
- Definitieve run: `data/block15_results_20261110T204340Z.json`
- Diagnostiek: `data/block15_diagnostics_diag_20261110T205129Z.json`
- Beoordelingen: `data/block15_assessments_20261110T204340Z.json`
- SQLite: `data/block15.sqlite3`
- Append-only JSONL: `data/block15_events.jsonl`
- Integriteitscontrole Block 1.5-JSONL: `{"valid": true, "events": 252, "error": null, "line": null}`
- Bestaande Block 1-data bleef onaangeroerd: `data/mdl.sqlite3` = 73728 bytes, `data/research_events.jsonl` = 24884 bytes, `mdl.cli verify-log` = valid met 20 events.
- Piloruns `block15_results_20261110T202848Z.json`, `block15_results_20261110T203527Z.json` en de losse A1-hertest `block15_results_20261110T204249Z.json` zijn bewaard maar **uitsluitend technische pilotruns**; ze zijn niet meegenomen in de scores.

### Compliance
- Geen nieuwe dependencies (`uv pip check` bleef schoon; `pytest` = 57 passed).
- Geen installatie, download, training of fine-tuning.
- Geen modelgegenereerde code uitgevoerd.
- Geen parallelle LFM3-requests.
- Geen bestaande experimentdata verwijderd of overschreven.
- Geen algemene conclusies getrokken over LFM3; dit is een eerste empirische nulmeting op 12 primaire taken.

---

## 1. Overzicht van alle experimenten

Definitieve run-ID: `20261110T204340Z`.  
Bron: `data/block15_results_20261110T204340Z.json`.

### Primaire taken: 12

| Taak-ID | Cat. | Moeilijk | Modus | Latency | Prompt / eval tokens | Calls | Resultaat in één regel |
|---|---:|---|---:|---:|---:|---:|---|
| `A1_coefficient_baseline` | A | medium | baseline | 43.9 s | 202 / 704 | 1 | Correcte afleiding naar 77, maar `answer`-veld zegt 4. |
| `A2_difference_terms` | A | hard | baseline | 44.4 s | 214 / 701 | 1 | Correcte redenering: 3 termen, som 64; `answer`-veld afgekapt. |
| `B1_counterexample` | B | medium | baseline | 17.1 s | 227 / 238 | 1 | Vindt n=33, maar niet kleinste tegenvoorbeeld n=16. |
| `B2_sequence_rule` | B | hard | baseline | 69.8 s | 225 / 1101 | 1 | `answer` 57/73 en verkeerde formule; redenering corrigeert naar 61/85 en 2n²−2n+1. |
| `C1_hypothesis_primality` | C | medium | baseline | 13.9 s | 231 / 179 | 1 | Precieze maar overgegeneraliseerde hypothese, geen concrete test. |
| `C2_hypothesis_last_digit` | C | hard | baseline | 11.6 s | 230 / 141 | 1 | Correcte hypothese en residue-controle. |
| `D1_even_proof` | D | medium | baseline | 7.3 s | 192 / 79 | 1 | Geldig kort bewijs: n(n+1) bevat een even getal. |
| `D2_false_primality_proof` | D | hard | baseline | 8.4 s | 196 / 96 | 1 | Correct weerlegd met n=40, 1681=41². |
| `E1_tool_coefficient` | E | medium | tool | 33.0 s | 726 / 391 | 2 | Correct 41472, maar model koos geen tool. |
| `E2_tool_divisibility` | E | hard | tool | 20.6 s | 0 / 0 | 0 | Mislukt door malforme JSON in toolbeslissing; geen eindantwoord. |
| `F1_error_correction` | F | medium | baseline | 7.3 s | 209 / 74 | 1 | Herkent fout en noemt juiste uitbreiding x²+2x+1. |
| `F2_revise_conclusion` | F | hard | baseline | 14.1 s | 245 / 181 | 1 | Herkijkt de conclusie; scheidt wat een tegenvoorbeeld wél en niet bewijst. |

Totaal primaire run: 12 tasks, 11 completed, 1 failed, 12 modelcalls, 291.4 s latency, 2897 prompt-tokens, 3885 eval-tokens.

### Controles: 3

| Controle | Verband | Latency | Prompt / eval | Calls | Observatie |
|---|---|---:|---:|---:|---|
| `A1_coefficient_tool` | baseline/tool-paar | 31.6 s | 683 / 378 | 2 | Correct 77; geen tool gebruikt. |
| `A1_coefficient_repeat` | exacte herhaling A1 | 45.1 s | 202 / 704 | 1 | Identiek aan A1, incl. fout antwoordveld. |
| `D1_even_proof_repeat` | exacte herhaling D1 | 7.5 s | 192 / 79 | 1 | Identiek correct bewijs. |

### Diagnostiek: 3, apart gelabeld

| Diagnostiek | Protocol / onderwerp | Observatie |
|---|---|---|
| `A1_coefficient_baseline_reasoning_first` | redenering-vóór-antwoord | Zelfde taak, schema met `reasoning` vóór `answer`, geeft correct `answer=77`. |
| `B2_sequence_rule_reasoning_first` | redenering-vóór-antwoord | Zelfde taak, schema met `reasoning` vóór `answer`, geeft correct 61, 85 en 2n²−2n+1. |
| `E2_tool_divisibility_forced` | expliciete toolaanvraag | Expliciete toolaanvraag gebruikt `^` → veilig afgewezen; model geeft daarna zelf correct antwoord. |

Totaal hoofdrun inclusief controles: 15 experiments, 14 completed, 1 failed, 16 modelcalls, 375.4 s latency, 3974 prompt-tokens, 5046 eval-tokens.

---

## 2. Score per categorie

Schaal: 0–4.  
0 = ontbrekend/mislukt; 1 = grote fouten; 2 = wisselend/tegenstrijdig; 3 = goed met kleine gebreken; 4 = volledig correct/geldig/volledig.

| Categorie | Correctheid | Logische geldigheid | Volledigheid | Zelfstandigheid | Onzekerheids-hantering | Samenvatting |
|---|---:|---:|---:|---:|---:|---|
| A — wiskundig redeneren | 2.00 | 3.50 | 3.00 | 4.00 | 1.50 | onderliggende redenering vaak sterk, uitvoercontract soms stuk |
| B — patroonherkenning | 1.50 | 3.50 | 2.00 | 4.00 | 1.00 | patronen worden herkend, minimaliteit/generalisatie faalt vaak |
| C — hypothesevorming | 3.00 | 3.00 | 3.00 | 4.00 | 2.50 | sterk waar de hypothese testbaar is, zwak bij vijf waarnemingen |
| D — bewijsvoering | 4.00 | 4.00 | 4.00 | 4.00 | 4.00 | sterk in kleine bewijzen en tegenvoorbeelden |
| E — toolgebruik | 2.00 | 2.00 | 2.00 | 3.00 | 2.00 | structureel zwak: tool wordt vermeden of verkeerd aangevraagd |
| F — zelfcorrectie | 4.00 | 4.00 | 3.50 | 4.00 | 4.00 | correct revisie en erkenning van misvattingen |
| **Totaal primair** | **2.75** | **3.33** | **2.92** | **3.83** | **2.50** | eerste nulmeting, geen algemeen oordeel |

Toolgebruik is alleen voor E numeriek: 1.00 van 4 over de twee E-taken. Herhaalbaarheid is alleen numeriek gemeten voor A1 en D1: beide exact identiek bij herhaling.

---

## 3. Sterke punten van LFM3 in deze eerste ronde

1. **Korte, exacte bewijzen.** D1 leverde een geldig bewijs dat `n(n+1)` product is van opeenvolgende getallen.
2. **Tegenvoorbeeld zoeken.** D2 vond direct n=40 en 1681=41².
3. **Misvatting herkennen.** F1 wees `(x+1)^2 = x^2+1` correct af en gaf juiste uitbreiding.
4. **Conclusie herzien met scope-bewustzijn.** F2 liet expliciet zien wat een tegenvoorbeeld wél en niet bewijst.
5. **Testbare hypothese vormen.** C2 formuleerde een correcte hypothese over laatste cijfers en deed een residuecontrole.
6. **Reproduceerbaar gedrag onder vaste seed.** A1 en D1 herhaalden exact: zelfde `answer`, zelfde `reasoning`, zelfde eval-tokens.
7. **Zelfcorrectie binnen redenering.** In A1, A2 en B2 zag het model zijn eigen fouten en bereikte het correcte resultaat in `reasoning`, al kwam dat niet in `answer`.

---

## 4. Structurele zwakke punten

1. **Antwoordveld versus redenering.**
   - A1: redenering concludet 77, `answer` zegt 4.
   - B2: redenering corrigeert naar 61,85 en 2n²−2n+1, `answer` blijft 57/73 en een verkeerde formule.
   - A2: `answer` eindigt midden in een afleiding en bevat geen bruikbare conclusie.
   Dit is een uitvoercontract-probleem: het schema zette `answer` vóór `reasoning`.

2. **Te grote neiging tot uitvoer en afkapping.**
   - De eerste pilotrun kapte antwoorden af op 600 tokens.
   - Ook met 1200 tokens bleef A2 het `answer`-veld op de maximale lengte vullen met de hele afleiding.

3. **Toolgebruik is zwak of vermijdend onder een vrijwillig protocol.**
   - Bij E1 en A1-tool koos het model bewust/onbewust geen `symbolic_expand`.
   - E2 faalde op malforme JSON in de toolbeslissing.
   - De geforceerde E2-diagnostiek gebruikte `^` in plaats van `**` en werd veilig afgewezen; daarna antwoordde het model correct zonder tool.

4. **Onzekerheids-hantering is niet gekalibreerd.**
   - B1 rapporteerde `confidence=1.0` terwijl het `uncertainty`-veld "High" zei.
   - A1 rapporteerde `confidence=0.95` ondanks een intern tegenstrijdig antwoord.

5. **Volledigheid van zoeken faalt.**
   - B1 vond een geldig tegenvoorbeeld, maar niet het kleinste; het controleerde niet alle kleinere n.

6. **Hypothesevorming uit weinig data blijft riskant.**
   - C1 stelde "prime iff n≤40" op uit vijf eerste waarden en gaf geen concrete falsificatieprocedure.

7. **JSON-robustheid.**
   - Meerdere taken produceerden malforme JSON door letterlijke regeleinden of afbreking in strings. Het huidige contract is dus nog niet productierijk voor automatische verwerking.

---

## 5. Interessante of onverwachte prestaties

- **A1 reproduceerbare fout exact:** 704 output-tokens met eindafleiding 77, maar `answer=4`. Exacte herhaling gaf exact dezelfde uitvoer en hetzelfde tokenaantal.
- **B2 toont zelfcorrectie in de verdere tekst:** de `reasoning` zegt expliciet "previous guess 57 was wrong", maar het eerder gegenereerde `answer`-veld wordt niet bijgewerkt.
- **A2 gebruikt een lange ketting van corrigerende redenering** en komt op het juiste 3-termen/64-antwoord, maar de machineleesbare conclusie blijft onbruikbaar.
- **C1 lijkt kennis van de Euler-polynomial te hebben** — het noemt de grens rond n=40 — maar vormt dit tot een ongefundeerde if-en-only-if-hypothese.
- **E2 geforceerd:** het model kent de juiste factoring `5xy(x+y)(x²+xy+y²)`, maar kan de toolgrammatica `**` niet toepassen wanneer de prompt `^` bevat.

---

## 6. Voorbeelden van fouten met uitleg

| Taak | Ruwe observatie | Onafhankelijke controle | Foutcategorieën | Uitleg |
|---|---|---|---|---|
| A1 | `answer=4`, `reasoning` eindigt op 77 | SymPy-coëfficiënt = 77 | 2, 8 | De afleiding is geldig, maar de eindconclusie in het antwoordveld is verkeerd en tegelijkertijd hoog zeker. |
| A2 | `answer` afgekapt, `reasoning` correct | SymPy: 3 termen, som 64 | 8, technische truncatie | Model vult `answer` met te lange afleiding; onterechte zekerheid 1.0 ondanks onbruikbare uitvoer. |
| B1 | Geeft n=33 met 1139=17·67 | Eerste falende waarde is n=16, 289=17² | 2, 8, 9 | Het tegenvoorbeeld voor 33 is geldig, maar de claim "kleinste" is onbewezen. Geen minimale zoekcontrole. |
| B2 | `answer=57,73`, n²+4n−3; `reasoning` corrigeert naar 61,85 | SymPy-interpolatie geeft 61,85 en 2n²−2n+1 | 2, 8 | Uitvoerveld is niet consistent met de redenering; tegenstrijdigheid volgt uit veldvolgorde/format. |
| C1 | Stelt "prime iff n≤40" uit 5 waarnemingen | P(41)=1681=41² | 4, 9 | Overgeneralisatie uit eindig bewijs; geen concrete test voorgesteld. |
| E2 | Tool-beslissing malforme JSON | Geen eindberekening mogelijk | 6, 9 | Onjuist toolgebruik/uitvoer; geen geldige aanvraag, dus geen interpretatie. |
| E2 forced | Gebruikt `^` in expressie | Orchestrator wijst af: illegal character `^` | 6 | Verkeerde toolgrammatica; veilige afwijzing werkte correct, maar tool gaf geen hulp. |
| F1 | `answer` zegt alleen "incorrect"; redenering bevat juiste uitbreiding | SymPy: x²+2x+1 | geen wiskundige fout | Mathematisch correct, maar antwoordveld is incompleet. |

Let op: C2, D1, D2 en F2 bevatten wel geldige bewijsredeneren. Een correct finaal antwoord zonder geldige redenering zou hier niet als "bewezen redeneren" zijn geclassificeerd; die scheiding is in de beoordelingen expliciet gemaakt.

---

## 7. Verschil tussen zelfstandig en tool-ondersteund werken

### Baseline
- Tien primaire taken werden zonder tool uitgevoerd.
- Hieruit is zichtbaar dat LFM3 sterke korte bewijzen en directe symbolische manipulatie kan.

### Tool-ondersteund
- E1: tool beschikbaar, maar gekozen werd niet; direct antwoord was correct.
- E2: tool beschikbaar, maar toolbeslissing was malforme JSON; er kwam geen toolresultaat.
- A1-tool controle: tool beschikbaar, maar niet gebruikt; antwoord was correct, terwijl baseline op dezelfde taak een fout antwoordveld gaf.
- E2 forced diagnostiek: expliciete toolaanvraag gebruikt `^`, wordt afgewezen; daarna antwoord zonder tool correct.

### Conclusie voor deze ronde
Er is **geen succesvolle `symbolic_expand`-uitvoering** in de hoofddbenchmark. De baseline/toolvergelijking is daarom nog zwak. Belangrijk onderscheid: verbetering van A1-tool ten opzichte van A1-baseline kan **niet** aan de tool worden toegeschreven, omdat de tool niet is gebruikt. De sterkste toekomstige observatie is protocolafhankelijkheid: als de tool expliciet wordt gevraagd, gebruikt het model hem wel, maar maakt dan grammaticafouten (`^` vs `**`). Block 1 toonde eerder al dat de gestuurde agent-loop een geldige toolaanvraag kan produceren.

---

## 8. Betrouwbaarheid en herhaalbaarheid

| Controle | Resultaat |
|---|---|
| A1 exacte herhaling | `answer`, `reasoning` en `eval_count` identiek; reproduceerbare fout. |
| D1 exacte herhaling | `answer`, `reasoning` en `eval_count` identiek; reproduceerbaar bewijs. |
| B1, B2 | Enkele run; geen herhaling, dus geen herhaalbaarheidsmeting. |
| E2 | Faalde in hoofdrun; diagnostiek toont dat wijziging van prompt/protocol/schema gedrag verandert. |
| Log-integriteit | Block 1.5-JSONL hash-chain valid; 252 events; SQLite 49 experiments, 105 steps. |
| Resource-stabiliteit | Geen stop door geheugen; free RAM 1495 MB bij start, 1356 MB bij einde, nooit onder 450 MB. |
| Modelherstel | `ollama stop lfm3:latest` slaagde; vrije RAM na ontladen 3118 MB, geen llama-server-proces. |

Interpretatie: binnen vaste seed/settings is LFM3 hier deterministisch. Tussen taken is het gedrag sterk gevoelig voor prompt, schema-veldvolgorde, toolprotocool en outputbudget.

---

## 9. Welke voorbeelden later waardevol kunnen zijn voor training

Preliminair, zonder iets toe te voegen aan een dataset:

### Mogelijk trainingswaardig
- `C2_hypothesis_last_digit` — correcte hypothese plus residuecontrole.
- `D1_even_proof` — compact, geldig bewijs.
- `D2_false_primality_proof` — correct tegenvoorbeeld met expliciete berekening.
- `F1_error_correction` — correct afwijzen van misvatting en juiste uitbreiding.
- `F2_revise_conclusion` — scope-bewuste revisie.
- Diagnostiek `A1_..._reasoning_first` en `B2_..._reasoning_first` zijn schone correcte traces, maar horen bij een diagnostisch protocol en niet automatisch bij de oorspronkelijke benchmarkopgaven.

### Voornamelijk evaluatiegeschikt
- `A1_coefficient_baseline`, `A1_coefficient_repeat`, `A2_difference_terms`
- `B1_counterexample`, `B2_sequence_rule`
- `C1_hypothesis_primality`
- `E1_tool_coefficient`, `A1_coefficient_tool`
- `E2_tool_divisibility_forced` — leerzame toolfout, maar geen trainingsdoel.

### Onduidelijk of ongeschikt
- `E2_tool_divisibility` hoofdrun — geen antwoord door output/tool-fout; geen nuttige target-trace.

---

## 10. Welke evaluatietaken apart moeten blijven van trainingsdata

Houd in de volgende fase expliciet apart:
1. **Klassieke counterexamples en bekende formules** — B1, C1, D2, B2. Risico op verontreiniging als dezelfde of herformulering straks in trainingsdata komt.
2. **Bewezen/valsbare statements** — D1, D2, C1, C2. Dit zijn sterke evaluatie-items omdat onafhankelijke controle eenvoudig is.
3. **Toolgebruikstaken** — E1, E2 en A1-tool. Houd ze uit training tot het toolprotocool en outputcontract stabiel zijn.
4. **Onderwerpspecifieke formuleringsvarianten** — houd nieuwe varianten gescheiden van standaardopgaven, anders meet je recall in plaats van regelbegrip.

Voor training in een latere fase gebruik bij voorkeur:
- zelfgegenereerde, moeilijker gemaakte varianten,
- correcte traces waarbij het antwoord pas ná de redenering wordt gezet,
- expliciete toolaanvragen met `**` en valide syntaxis,
- tegenvoorbeeldzoekopdrachten met bewijs van minimaliteit.

---

## 11. Aanbevelingen voor de volgende onderzoeksfase

1. **Verander eerst het outputcontract, niet het model.**
   Zet `reasoning` vóór `answer` in het JSON-schema. De diagnostics lieten precies dit effect: A1 en B2 veranderden van tegenstrijdig naar correct.

2. **Scheid "machineleesbaar antwoord" van "ruwe modeltekst" in scoring.**
   De ruwe tekst bevatte vaak de juiste wiskunde; het `answer`-veld was het faalende onderdeel.

3. **Maak het toolgebruik expliciet en tweestaps.**
   Eerst een strikte `symbolic_expand`-aanvraag, dan validatie, dan interpretatie. De geforceerde E2-test toont aan dat vrijwillige toolkeuze kan leiden tot vermijding.

4. **Voeg een grammaticahint in toolprompts.**
   De E2-toolaanvraag gebruikte `^`. Een expliciete herinnering "gebruik `**`, geen `^`" is nodig.

5. **Controleer minimaliteit en volledigheid.**
   B1 moet in toekomstige versies expliciet vragen naar een zoekrange en bewijs dat geen kleiner tegenvoorbeeld bestaat.

6. **Meet onzekerheid strikter.**
   Penaliseer interne tegenstrijdigheden: `confidence=1.0` naast `uncertainty=High` of `answer≠reasoning` is een fout.

7. **Breid het aantal taken pas na het stabiliseren van het uitvoercontract.**
   Twaalf taken is een nulmeting. Twaalf tot vierentwintig nieuwe varianten zijn pas zinvol nadat het contract reproduceerbaar is.

8. **Houd Block 1 als sandbox en maak Block 1.5 losse benchmarkmodules.**
   De `block15`-aanpak werkte goed: Block 1 bleef onaangeroerd, tests bleven 57 passed, data bleef append-only.

---

## Slotstatus

- Block 1: **ongewijzigd**, tests blijven slagen.
- Block 1.5 ronde 1: **afgerond**, data en beoordelingen opgeslagen.
- Geen training gestart.
- Geen Block 2 gebouwd.
- Niets gedownload.
- **Ik stop hier en wacht op beoordeling door ChatGPT.**
