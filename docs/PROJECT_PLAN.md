# RetailLens project plan

## Cel i odbiorca

Zbuduj B1 RetailLens: lokalny projekt analityczny marketplace, pokazujący cały
proces od danych do decyzji. Odbiorca raportu porównuje wartość zamówień,
terminowość, oceny i jakość danych. Odbiorca techniczny może odtworzyć analizy
oraz sprawdzić SQL, DAX, model, testy i decyzje.

Projekt ma odpowiadać na pięć pytań:
1. Jak zmieniają się liczba i wartość kwalifikujących zamówień?
2. W jakich segmentach obserwujemy problem terminowości?
3. Jak różnią się oceny między grupami terminowości, z jakimi liczebnościami?
4. Jak uzgadniają się kwoty pozycji i dostawy z płatnościami?
5. Jaki jest obserwowany udział ponownych zakupów w porównywalnym oknie?

## Przyjęta architektura

Python 3.12 w układzie src/retaillens oraz tests; PostgreSQL i SQL; jeden
Dockerfile aplikacji oraz docker-compose.yml; Power BI PBIP, TMDL, PBIR, DAX,
Power Query w trybie Import. Ruff, pytest i GitHub Actions z template.

Przepływ: oficjalne pliki Olist lub jawny fixture -> raw z pochodzeniem ->
typowane tabele staging -> marty analityczne -> Power BI i wyniki zapytań SQL.
Real i synthetic nie są mieszane w tych samych tabelach/wynikach bez jawnej
separacji. Wybierz osobne schematy lub osobne bazy i opisz decyzję.

Zakres zawiera PostgreSQL, nie wszystkie silniki wymienione w ogólnym template.
Drugi frontend, dbt, Airflow, Spark, Kafka i chmura są poza tym MVP. Nie dodawaj
ich jako zastępstwa niedostępnego Power BI Desktop.

Rozszerz istniejące katalogi o powerbi/ oraz output/ (wyniki lokalne, poza Git).
Kod importu i transformacji musi mieć CLI lub równoważne powtarzalne komendy.
Skrypty PowerShell uruchamiają te komendy; nie zawierają oddzielnej logiki KPI.

## Etapy wewnętrzne

### 00 Uruchomienie i pierwsze dane

Potwierdź repo i środowisko. Utwórz gałąź, świeże lokalne środowisko Python,
zależności i odtwarzalne wersje. Sprawdź oficjalne źródło oraz próbkę. Przygotuj
deterministyczny fixture i oczekiwane wyniki. Uruchom pierwszy rzeczywisty
przebieg profilowania. Doprecyzuj kontrakt na podstawie schematu, nie na podstawie
założonych wyników biznesowych. Przejdź do 01 bez osobnego zatwierdzenia.

### 01 Import i PostgreSQL

Zbuduj Compose, odczyt konfiguracji i import źródłowych CSV. Zachowuj oryginalne
pliki, SHA256, numery wierszy, wersję, zakres dat i liczności. Rejestruj przebiegi
oraz odrzucenia. Ponowny import tej samej wersji ma dać ten sam stan. Błąd importu
nie może zostawić częściowo opublikowanego zestawu. Żaden reset nie usuwa
niepowiązanych danych ani istniejących wolumenów.

### 02 Model analityczny

Zaimplementuj marty z docs/DATA_CONTRACT.md. Opisz klucze, grain, relacje, typy,
populacje KPI i wyłączenia. Osobno agreguj pozycje, płatności i opinie przed ich
połączeniem. Testuj model na PostgreSQL. Wykaż poprawność trudnych przykładów
z wieloma pozycjami, równymi cenami, płatnościami i opiniami.

### 03 Analizy i wnioski

Napisz zapytania do pięciu pytań, policz wyniki dla przypiętego wejścia i zapisz
ich eksport z parametrami. Uwzględnij okna obserwacji, niepełne okresy i wyłączenia.
Przygotuj do trzech najlepiej udokumentowanych ustaleń: wynik -> dowód SQL ->
interpretacja -> możliwe następne działanie -> ograniczenie. Brak podstaw do
wniosku jest poprawnym rezultatem. Jeśli źródło realne jest niedostępne, zapisz
wyłącznie wyniki fixture oraz dokładną listę niewykonanych analiz Olist.

### 04 Kompletny raport Power BI

Dostarcz powerbi/RetailLens.pbip, lokalny model TMDL i raport PBIR. Zbuduj
rzeczywiste strony z wizualizacjami powiązanymi z miarami, nie same pliki DAX.
Model ma parametry hosta/portu/bazy; hasło pozostaje w lokalnym mechanizmie
poświadczeń. Desktop na hoście używa portu opublikowanego na localhost,
a klient w Compose nazwy usługi i portu wewnętrznego.

Cztery strony:
1. Overview: liczności, delivered GMV, delivered AOV, trend, obserwowane powroty,
   zakres i kompletność danych.
2. Deliveries and reviews: terminowość, opóźnienia, segmenty, rozkład ocen
   i liczebność/kompletność grup.
3. Sellers and categories: wartość pozycji, udział segmentów i porównania
   z właściwą szczegółowością; terminowość sprzedawcy tylko w jawnej populacji.
4. Data quality: odrzucenia, braki, niejednoznaczności, uzgodnienie kwot
   i możliwość znalezienia zamówienia powodującego rozbieżność.

Raport ma spójne tytuły, jednostki, liczebności, filtry, opisy i natywne
wizualizacje. Każdy KPI ma zdefiniowane interakcje z filtrami.
Wykonaj walidację formatów i odwołań. Jeśli jest dostępny Desktop/silnik,
otwórz raport, odśwież, porównaj DAX z SQL i obejrzyj wszystkie cztery strony.
Brak runtime nie zatrzymuje 05; niewykonane kontrole pozostają NOT_RUN.

### 05 Odtworzenie i materiał do portfolio

Dokończ README EN: problem, architektura, dane, setup, komendy, wyniki, testy,
ograniczenia i dalszy rozwój. Dodaj docs/CASE_STUDY.md, docs/ARCHITECTURE.md
oraz docs/DEMO.md z trzyminutowym scenariuszem. Zrzuty mogą pochodzić tylko
z realnie wyrenderowanego raportu, z oznaczeniem trybu danych.
Przygotuj skrypty setup.ps1, demo.ps1, verify.ps1 i make_review_bundle.py
(nazwy można zmienić spójnie w dokumentacji). Sprawdź ich rzeczywiste działanie
w dostępnych środowiskach. Rozszerz CI o PostgreSQL na fixture i build obrazu.
Zapisz wynik końcowy i kompaktowy pakiet do review.

## Warunki ukończenia

- Jedna opisana ścieżka uruchamia lokalne demo bez ręcznego wykonywania SQL.
- Ponowienie importu nie zmienia liczności i KPI dla tego samego wejścia.
- Testy merytoryczne działają na PostgreSQL i kontrolnych danych.
- Zapytania odpowiadają na wszystkie pięć pytań; wyniki mają pochodzenie.
- Raport zawiera model, połączenie, miary oraz wszystkie cztery strony PBIR.
- JSON/TMDL, Desktop open, refresh, DAX i oględziny mają oddzielne dowody.
- Pełne DONE wymaga realnych danych i wykonania wszystkich bramek raportu.
  Jeśli pozostaje zewnętrzna blokada, status końcowy to PARTIAL z precyzyjną
  listą braków. Nie deklaruj działającego dashboardu po samym parsowaniu plików.
- Zależności, instrukcje, pipeline, testy i paczka review są odtwarzalne.
