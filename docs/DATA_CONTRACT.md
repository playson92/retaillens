# RetailLens analytical contract

Proponowane reguły MVP, 7 października 2026. To specyfikacja implementacji,
nie wyniki badania pobranego zbioru. Zweryfikuj nazwy i unikalność na wejściu.
Jeśli źródło przeczy założeniu, zachowaj surowe dane, opisz fakt i wprowadź
uzasadnioną zmianę kontraktu, bez ukrywania utraconych rekordów.

Implementation evidence (run 20261007T191556Z): official Olist v2 schemas and candidate
keys were profiled. The original spelling of product *_lenght fields is retained.
All required candidate keys were unique on these actual inputs; review rows deliberately
have no business uniqueness constraint. Typed duplicate conflicts remain an explicitly
tested fixture case. Blank optional values are retained as NULL, invalid fields also get
issues, and raw source strings stay available.

Real study observation boundary: start of 2018-09-01, an explicit completeness assumption.
The profiled September/October source tail has 16/4 orders and zero delivered orders;
it is not used to extend repeat follow-up. CLI without an explicit boundary defaults
conservatively to start of the maximum valid source purchase day, with its assumption
recorded. Do not compare these different observation choices without matching parameters.

Chronology implementation additionally checks approval/carrier timestamps when present:
purchase <= approval <= actual, purchase <= carrier <= actual, approval <= carrier.
Missing approval/carrier fields alone do not exclude a delivery. Rejected item/payment
keys prevent a remaining partial monetary side being marked complete. Unknown seller
identity or rejected items exclude single-seller attribution. Quality counts can overlap.

## Pochodzenie i model

- raw: jeden rekord konkretnego pliku, klucz file_sha256 + source_row_number.
- orders: jeden order_id, status, customer_id i daty procesu.
- order_items: kandydat klucza (order_id, order_item_id). Numer pozycji nie
  jest ilością do pomnożenia przez cenę.
- order_payments: kandydat (order_id, payment_sequential). Nie mnożyć
  payment_value przez payment_installments.
- order_reviews: zachować wszystkie wiersze z pochodzeniem; nie zakładać
  unikalności samego review_id ani order_id.
- customers: mapowanie customer_id do customer_unique_id. Lokalizacja
  pochodzi z rekordu zamówienia; nie zakładać jej niezmienności dla osoby.
- mart_orders: dokładnie jeden order_id, po oddzielnej agregacji pozycji,
  płatności i opinii. Dodatkowo mart_items, wymiar daty, produktu, sprzedawcy
  i niewielki mart kohort powrotów. Opisz kierunki filtrów i zapobiegaj
  niejednoznacznym ścieżkom relacji.

Nie sumuj na iloczynie pozycji, płatności i opinii. SUM(DISTINCT price) nie
naprawia powielonego połączenia, bo dwie legalne pozycje mogą mieć równą cenę.
Konfliktujące klucze i osierocone rekordy mają raport, nie losowy wybór wiersza.
Pieniądze: Decimal i PostgreSQL NUMERIC, jawna waluta oraz jednostka. Nie
używaj binarnego float do ustalania zgodności sum pieniężnych.

Do analizy ocen wybierz jedną najpóźniejszą poprawną odpowiedź na zamówienie
według review_answer_timestamp. Przy sprzecznych ocenach z tym samym
najpóźniejszym czasem oznacz niejednoznaczność i wyłącz z analizy ocen.
Zachowaj wszystkie źródłowe opinie oraz liczność wyłączeń.

## M1 Delivered GMV

Populacja: status delivered, poprawna data zakupu, co najmniej jedna pozycja
i komplet poprawnych price dla zamówienia.
Wartość = suma price kwalifikujących pozycji. Bez freight i bez kwot płatności.
Okres = data zakupu. Brak price w którejkolwiek pozycji wyłącza całe zamówienie
z tej populacji. Etykieta informuje, że miara dotyczy dostarczonych zamówień.
To wartość towarów w wycinku źródła, nie zysk i nie księgowy przychód operatora.

## M2 Delivered AOV

M1 / liczba różnych order_id z dokładnie tej samej populacji.
Przy zerowym mianowniku wynik pusty z komunikatem. Nie uśredniaj miesięcznych
średnich. Przy filtrze kategorii/sprzedawcy suma jego pozycji na zamówienie
ma inną etykietę, np. Segment item value per order. Nie udawaj pełnego AOV.

## M3 On time delivery rate

Osobna populacja: dostarczone zamówienia z poprawną datą zakupu, obiecaną
i faktyczną datą dostawy, bez sprzecznej chronologii. Braki kwot nie wyłączają
automatycznie z analizy terminowości.
Terminowe = DATE(order_delivered_customer_date) <= DATE(order_estimated_delivery_date).
Obietnica jest dniem kalendarzowym: DATE(estimated) >= DATE(purchase).
Północ w obiecanym dniu zakupu nie oznacza zdarzenia sprzed zakupu.
Approval, carrier i actual pozostają zdarzeniami porównywanymi pełnym timestampem.
Porównuj dni źródłowe; nie przypisuj naiwnym timestampom UTC bez podstawy.
Wynik = liczba terminowych / liczba kwalifikujących dostarczonych.
Braki i niedostarczone pokazuj osobno; nie klasyfikuj ich automatycznie jako
spóźnionych. Przy pustym mianowniku wynik pusty.

## M4 Payment reconciliation

Na poziomie zamówienia:
expected_amount = SUM(price + freight_value) po pozycjach
paid_amount = SUM(payment_value) po płatnościach
delta = paid_amount - expected_amount

Tolerancja projektu: ABS(delta) <= 0.01, konfigurowalna i zapisana w wyniku.
matched: obie strony kompletne, różnica w tolerancji.
mismatch: obie strony kompletne, różnica poza tolerancją.
not_comparable: braki lub błędy uniemożliwiają obliczenie jednej ze stron.

Domyślny udział dla dostarczonych = matched / (matched + mismatch).
Obok pokaż udział i liczność not_comparable. Udostępnij diagnostykę wszystkich
statusów. Różnica nie jest automatycznie refundacją, stratą ani odsetkami.
Uzgodnienie nie stanowi dowodu kompletności księgowej.

## M5 Observed repeat purchase within 90 days

Osoba = customer_unique_id. Pierwszy zakup = pierwszy zaobserwowany dostarczony
order_id w całym dostępnym źródle, ustalony przed filtrem okresu raportu.
Kohorta raportu obejmuje osoby z pierwszym zakupem w wybranym okresie i
co najmniej 90 dniami dalszej obserwacji w przyjętym zakresie źródła.
Sukces = inny dostarczony order_id, o późniejszym czasie zakupu, nie później
niż 90 dni od pierwszego. Jawnie opisz przypadki równych timestampów.
Wynik = osoby z sukcesem / kwalifikujące osoby z pełnym przyjętym oknem.

Zapisz granicę obserwacji i podstawę jej wyboru. Nie nazywaj daty maksymalnego
rekordu dowodem kompletności źródła. Bez podstaw do przyjęcia okna wynik jest
oznaczony jako nieoceniony albo oparty na jawnym założeniu zakresu obserwacji.
Nie używaj bieżącego zegara jako końca historycznej obserwacji.
Wykluczone niepełne okna mają liczność. Pierwszy zaobserwowany zakup nie musi
być pierwszym zakupem klienta w rzeczywistości. Nie nazywaj tej miary churn/CLV.
W MVP miara reaguje na okres pierwszego zakupu; filtry produktu i sprzedawcy
jej nie zmieniają, co raport musi jasno komunikować.

## Okresy, segmenty i oceny

- Zapisz analysis_start, analysis_end_exclusive i observation_end z uzasadnieniem.
  Profiluj rozkład dni/miesięcy i statusów. Nie hardkoduj pełnych miesięcy
  na podstawie samego opisu lat 2016–2018.
- Pierwszy i ostatni obserwowany miesiąc domyślnie nie trafiają do porównań
  MoM/YoY; wewnętrzny miesiąc sam w sobie nie dowodzi pełnego pokrycia źródła.
- Filtr daty zakupu nie obcina automatycznie późniejszej dostawy i opinii.
- GMV sprzedawcy/kategorii licz po jego pozycjach. Płatności całego zamówienia
  nie stają się płatnościami danego sprzedawcy bez udokumentowanej alokacji.
- Terminowość i oceny sprzedawcy w MVP ogranicz do zamówień jednosprzedawcowych;
  pokaż wyłączenie wielosprzedawcowych. Nie przypisuj przyczyny opóźnienia.
- Porównanie ocen ma jedno zamówienie na obserwację, liczebności i udział opinii.
  Korelacja nie dowodzi skutku planowanej interwencji.
- Porównuj SQL i DAX na identycznych populacjach i jawnych zestawach filtrów.

## Małe przykłady z oczekiwanym wynikiem

1. Dwa kwalifikujące zamówienia o wartości towarów 100 i 50: GMV 150, AOV 75,
   niezależnie od liczby płatności/opinii.
2. Pozycje 40 i 60, dostawa 5 i 5, płatności 70 i 40: expected 110, paid 110,
   delta 0. Liczba rat nie zmienia sumy.
3. Dwie pozycje po 40: suma 80, a nie 40.
4. Faktyczna dostawa o 18:00 w obiecanym dniu jest terminowa; dzień później
   jest spóźniona; brak daty jest wyłączeniem.
5. Dwa customer_id z tym samym customer_unique_id mogą oznaczać powrót.
   Klient bez pełnego okna 90 dni nie trafia do mianownika.
6. Sprzeczne najpóźniejsze opinie są oznaczone, nie wybrane przypadkowo.
7. Ponowny import i ponowna budowa modeli zachowują wyniki.
8. Te same przykłady w SQL oraz działającym silniku DAX dają zgodne miary.
