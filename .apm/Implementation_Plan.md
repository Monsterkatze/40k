# Nährwert-JPG Generator – APM Implementation Plan
**Memory Strategy:** Dynamic-MD
**Last Modification:** Updated Task 4.2 scope based on Task 4.1 findings (short-profile status tuning, parser warning-noise reduction, ingestion-reject failure surfacing).
**Project Overview:** Ein einmalig genutztes lokales Python-CLI verarbeitet eine große Produkt-CSV (~40k), klassifiziert und parst inkonsistente Nährwerttexte, validiert Ergebnisse, rendert nur bei verwertbaren Nährwerten standardisierte 1200x1200 JPGs, und erstellt Reports inklusive separater Review/Failed-Listen.

## Phase 1: Audit & Foundations

### Task 1.1 – CLI Scaffold & Runtime Config - Agent_Ingestion
**Objective:** Ein minimales, robustes lokales CLI-Programm mit den vereinbarten Laufparametern bereitstellen.
**Output:** Ausführbarer CLI-Einstieg mit Parametern und Basiskonfiguration.
**Guidance:** Nutze ein simples One-off-Design ohne Overengineering; Parameterfokus auf `--input`, `--output`, `--workers`, `--resume`, `--limit`.
1. Erstelle Python-CLI-Entry mit klaren Argumenten und sinnvollen Defaults (`workers=6`, `resume=true`).
2. Implementiere zentrale Laufkonfiguration für Input-/Output-Pfade, Parallelisierung und Limitmodus.
3. Integriere konsistente Fehlerbehandlung für ungültige Parameter und fehlende Eingabedatei.
4. Initialisiere Lauf-Logging (Konsole + Datei `run.log`) als gemeinsame Basis für alle Phasen.

### Task 1.2 – CSV Ingestion & Encoding Robustness - Agent_Ingestion
**Objective:** CSV-Daten robust einlesen und in ein standardisiertes internes Datensatzformat überführen.
**Output:** Normalisierte Datensätze mit verlässlichen Kernfeldern (`id`, `name`, Nährwert-Rohtext).
**Guidance:** Berücksichtige deutsche Sonderzeichenprobleme und inkonsistente Quelldaten; Parsing muss speicherschonend sein.
1. Implementiere CSV-Reader mit Trennzeichenunterstützung (`;`) und Encoding-Fallback-Reihenfolge (`utf-8-sig` → `cp1252` → `latin-1`).
2. Normalisiere Spaltenzuordnung tolerant auf reale Header-Varianten (z. B. `Nährwerte` mit Encoding-Artefakten).
3. Führe zeilenweise Ingestion mit schlankem Speicherprofil aus und validiere Pflichtfelder (`id`, `name`).
4. Erzeuge einen bereinigten Stream/Datensatzcontainer als Input für Klassifikation und Parsing.

### Task 1.3 – Cell Classification Engine - Agent_Classification
**Objective:** Jede Nährwertzelle anhand definierter Signale in die Zielkategorien klassifizieren.
**Output:** Klassifizierte Datensätze mit Kategorien `MISSING`, `INGREDIENTS`, `NUTRITION`, `MIXED`, `UNKNOWN`.
**Guidance:** **Depends on: Task 1.2 Output by Agent_Ingestion**; Regeln strikt nach Spezifikation, inklusive Mindestsignal-Logik.
1. Implementiere Signalsets für Zutaten- und Nährwert-Erkennung inklusive deutscher Schreibvarianten.
2. Baue Klassifikationslogik mit Prioritätsregeln (u. a. `MIXED` bei kombinierter Signal-Lage).
3. Stelle sicher, dass mindestens zwei Nährwertsignale für `NUTRITION` erforderlich sind.
4. Ergänze diagnostische Marker pro Zeile für spätere Audit-/Optimierungszwecke.

### Task 1.4 – Audit Report & Baseline Metrics - Agent_Classification
**Objective:** Eine erste Audit-Sicht über Datenqualität und Kategorien als Grundlage für die Parserphase erzeugen.
**Output:** Audit-Artefakt mit Kategorieverteilung, Stichproben-Snippets und Problemclustern.
**Guidance:** **Depends on: Task 1.3 Output**; liefere klare Prioritäten für parserseitige Robustheitsfälle.
- Aggregiere Verteilungen pro Kategorie und identifiziere dominante Problemtypen.
- Erzeuge eine kompakte Liste repräsentativer Problembeispiele (`UNKNOWN`, stark fehlerhafte Encodings, Mischtexte).
- Dokumentiere Baseline-Kennzahlen für späteren Vorher/Nachher-Vergleich.

## Phase 2: Parsing & Validation

### Task 2.1 – Text Normalization Pipeline - Agent_Parsing
**Objective:** Rohtexte in eine parserfreundliche, konsistente Form überführen.
**Output:** Normalisierter Nährwerttext je Produkt mit stabiler Zahlen-/Formatbasis.
**Guidance:** **Depends on: Task 1.2 Output by Agent_Ingestion**; beachte explizit Tausender-/Dezimal-Konvertierungen gemäß Spezifikation.
1. Entferne problematische Quotes, ersetze NBSPs und normalisiere Tabs/Mehrfachspaces.
2. Normalisiere deutsche Zahlformate inkl. Spezialfall `2.294,00 -> 2294.00`.
3. Vereinheitliche Tokenisierung für robuste Feldsuche trotz inkonsistenter Schreibweisen.
4. Markiere unparsebare Fragmente für spätere Warnungen statt harter Abbrüche.

### Task 2.2 – Nutrition Field Extraction Parser - Agent_Parsing
**Objective:** Nährwerte aus normalisiertem Text in die definierte Zielstruktur extrahieren.
**Output:** Strukturierte Felder (`kJ`, `kcal`, `fat_g`, `satfat_g`, `carbs_g`, `sugar_g`, `protein_g`, `salt_g`, `fiber_g`).
**Guidance:** **Depends on: Task 2.1 Output**; Synonyme, Einheitstransformationen und MIXED-Regeln sind verpflichtend.
1. Implementiere Synonym-Mapping für alle spezifizierten Nährwertfelder.
2. Extrahiere Zahlenwerte robust gegen verschiedene Schreibmuster (`:`, `/`, tabellarisch, Fließtext).
3. Unterstütze Einheiten `kJ`, `kcal`, `g` sowie `mg -> g` Konvertierung.
4. Setze Defaultannahme `g`, wenn bei Makronährstoffen keine Einheit vorhanden ist.
5. Für `MIXED`: parse ab `Nährwerte:` oder alternativ ab erstem Nährwertsignal.
6. Trage fehlende/unlesbare Felder als `null` ein statt Abbruch.

### Task 2.3 – Validation & Product Status Assignment - Agent_Validation
**Objective:** Extrahierte Werte plausibilisieren und pro Produkt einen verlässlichen Status vergeben.
**Output:** Validierte Datensätze mit Status `OK`, `OK_WITH_WARNINGS`, `NEEDS_REVIEW`, `FAILED` und Warnungsdetails.
**Guidance:** **Depends on: Task 2.2 Output by Agent_Parsing**; Plausibilitätsgrenzen strikt nutzen, Fehlertoleranz priorisieren.
1. Implementiere Range-Checks pro 100g (`kcal`, `kJ`, `Fett`, `Zucker`, `Salz`) mit Warning-Flagging.
2. Berechne `parsed_fields_count` und markiere Datensätze mit <3 validen Werten als `NEEDS_REVIEW`.
3. Definiere harte `FAILED`-Kriterien für vollständig unbrauchbare oder kritisch defekte Datensätze.
4. Sammle verständliche Warnungsgründe pro Produkt für Report und spätere Nacharbeit.

### Task 2.4 – Reporting Core & Split Review Exports - Agent_Validation
**Objective:** Vollständige Berichterstattung für operativen Run und manuelle Nachbearbeitung bereitstellen.
**Output:** `report.csv` plus separate CSVs für `NEEDS_REVIEW` und `FAILED` sowie Status-/Kategorie-Statistik.
**Guidance:** **Depends on: Task 2.3 Output**; Report muss idempotent, klar filterbar und manuell nutzbar sein.
1. Generiere `report.csv` mit Feldern `id`, `name`, `category`, `status`, `parsed_fields_count`, `warnings`, `raw_snippet`.
2. Schreibe getrennte Exporte für `NEEDS_REVIEW` und `FAILED`.
3. Ergänze zusammenfassende Statistik pro Kategorie und Status am Laufende.
4. Kürze `raw_snippet` deterministisch für gute Lesbarkeit und stabile Dateigröße.

## Phase 3: Rendering & Batch Execution

### Task 3.1 – Nutrition JPG Renderer (1200x1200) - Agent_Rendering
**Objective:** Einheitliche Nährwert-JPGs gemäß Formatvorgabe erzeugen.
**Output:** Rendering-Modul auf Pillow-Basis mit weißem Hintergrund und konsistentem Schriftbild.
**Guidance:** Render nur für verwertbare Nährwertfälle (`OK`, optional `OK_WITH_WARNINGS`), keine Bilder für reine Zutaten-/Missing-Fälle.
1. Implementiere 1200x1200-Canvas mit weißem Hintergrund und lesbarer, konsistenter Typografie.
2. Definiere ein fixes Nährwert-Layout mit allen Zielstrukturfeldern und `null`-sicherer Darstellung.
3. Kapsle Renderer als wiederverwendbare Funktion mit stabiler Fehlerbehandlung je Produkt.

### Task 3.2 – Output Sharding, Resume Skip & Worker Pipeline - Agent_Runtime
**Objective:** Massenverarbeitung performant und absturzarm ausführen.
**Output:** Batch-Engine mit Sharding (`output/<id-prefix>/<id>.jpg`), Resume-Skip und Parallelisierung.
**Guidance:** **Depends on: Task 3.1 Output by Agent_Rendering**; **Depends on: Task 2.4 Output by Agent_Validation**.
1. Implementiere Zielpfad-Sharding basierend auf ID-Präfix (z. B. `output/28/28274.jpg`).
2. Führe Resume-Logik ein: existierende Dateien werden standardmäßig übersprungen.
3. Integriere Worker-basierte Parallelisierung mit konfigurierbarem Default (`6`).
4. Verarbeite Einzelproduktfehler isoliert, damit der Gesamtlauf stabil weiterläuft.

### Task 3.3 – End-to-End Run Command & Operational Logging - Agent_Runtime
**Objective:** Den vollständigen Pipeline-Lauf als verlässlichen One-off-Command bereitstellen.
**Output:** End-to-End-Ausführung inkl. Fortschritt, Laufmetriken und klaren Abschlussartefakten.
**Guidance:** **Depends on: Task 1.1 Output by Agent_Ingestion**; **Depends on: Task 2.4 Output by Agent_Validation**; **Depends on: Task 3.2 Output**.
1. Verbinde Ingestion, Klassifikation, Parsing, Validierung, Rendering und Reporting in einem klaren Ablauf.
2. Integriere Fortschritts- und Ergebnislogging (Konsole + `run.log`) mit verständlichen Fehlermeldungen.
3. Unterstütze Testmodus (`--limit`) für kurze Vorabprüfung vor dem Vollrun.
4. Stelle sicher, dass der Lauf auch bei Teilfehlern deterministisch abschließt.

## Phase 4: Optimization & Acceptance

### Task 4.1 – Failure Pattern Analysis - Agent_Optimization
**Objective:** Häufige Ursachen in `NEEDS_REVIEW`/`FAILED` systematisch identifizieren.
**Output:** Priorisierte Fehlerklassen mit konkreten Verbesserungsansätzen für Parserregeln.
**Guidance:** **Depends on: Task 2.4 Output by Agent_Validation**; **Depends on: Task 3.3 Output by Agent_Runtime**.
1. Analysiere Review-/Failed-Exporte nach wiederkehrenden Mustern (Encoding, Einheiten, Mischtexte, Sonderfälle).
2. Gruppiere Ursachen nach erwarteter Hebelwirkung auf die Auto-Korrektheitsrate.
3. Leite daraus priorisierte Regelanpassungen mit geringem Implementierungsaufwand ab.

### Task 4.2 – Rule Tuning Loop & Controlled Re-run - Agent_Optimization
**Objective:** Parser-/Validierungsregeln iterativ verbessern und Wirkung kontrolliert messen.
**Output:** Verfeinerte Regelsets und dokumentierter Vorher/Nachher-Effekt.
**Guidance:** **Depends on: Task 4.1 Output**; erst auf Teilmenge testen, dann Vollrun; behebe auch identifizierte Observability-Lücke zwischen Ingestion-Skips und `FAILED`-Export.
1. Implementiere gezielte Regelanpassungen basierend auf den priorisierten Fehlerclustern.
2. Reduziere Warning-Noise bei bereits erfolgreich extrahierten Feldern (insb. `kcal`) und schärfe Statuslogik für kurze, valide Nährwertprofile.
3. Sorge für kompatible Sichtbarkeit von Ingestion-Rejects in Failure-Reporting/Statistik ohne Pipeline-Stabilität zu verlieren.
4. Führe einen kontrollierten Testlauf (z. B. `--limit 500`) zur schnellen Wirksamkeitsprüfung aus.
5. Rolle nur wirksame Anpassungen in den Vollrun aus und protokolliere Veränderungen in Statusverteilungen.

### Task 4.3 – Acceptance Check & Final Handover - Agent_Optimization
**Objective:** Abschlussqualität einfach, nachvollziehbar und entscheidungsfähig nachweisen.
**Output:** Finale Abnahmezusammenfassung mit Erfolgsquote, Restrisiken und Nacharbeitsliste.
**Guidance:** **Depends on: Task 4.2 Output**; verwende vereinbarte einfache Erfolgsmessung (200er Stichprobe, Ziel >=80%).
1. Ziehe eine zufällige Stichprobe von 200 Produkten aus den automatisch verarbeiteten Fällen.
2. Dokumentiere manuelle Korrektheitsprüfung und berechne Trefferquote (Ziel mindestens 160/200 korrekt).
3. Erstelle Abschlusszusammenfassung mit finalen KPIs, offenen Restfällen und klarer One-off-Handover-Notiz.

