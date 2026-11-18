# Projekt: symulacja i autonomiczne wykonywanie misji drona

Dokument porządkuje założenia projektu. Opisuje planowany system, a nie stan jego implementacji. Wskazane alternatywy, hipotezy i otwarte decyzje pozostają nierozstrzygnięte.

Zasady pracy nad repozytorium opisuje [AGENTS.md](AGENTS.md).

## 1. Cel projektu

Utworzenie narzędzia umożliwiającego:

- Symulację wykonania misji drona w różnych konfiguracjach: klasycznej i quadkoptera.
- Obserwację przebiegu wykonywanej misji.
- Symulację informacji z czujników w sposób zbliżony do rzeczywistości, bez zbędnego komplikowania środowiska.
- Późniejsze podłączenie rzeczywistych czujników dzięki wspólnym abstrakcjom.
- Wykorzystanie gotowej architektury modelu decyzyjnego i wytrenowanie jej w środowisku symulacyjnym.
- Uwzględnienie w treningu wielu implementowanych modułów opisanych w tym dokumencie.
- Inferencję prowadzącą od danych z czujników i poleceń użytkownika do ostatecznego działania drona.

## 2. Podział systemu

System obejmuje dwa główne obszary:

| Obszar | Odpowiedzialność |
| --- | --- |
| Stacja naziemna | Przyjmowanie poleceń operatora przez LLM lub GUI, przetwarzanie instrukcji i przekazywanie ich do drona. |
| Dron | Odbieranie poleceń, interpretacja dostępnych informacji o otoczeniu, podejmowanie decyzji i wykonywanie misji. |

Pierwsze środowisko wykonania drona będzie symulowane. Integracje należy opakować w abstrakcje pozwalające później podłączyć rzeczywiste komponenty.

## 3. Stacja naziemna

### 3.1. Sterowanie przez LLM

Przewidziano cztery rodzaje instrukcji:

| Instrukcja | Znaczenie |
| --- | --- |
| `SYSTEM` | Generalna dyrektywa definiująca ogólne przeznaczenie drona. |
| `GENERAL_INSTRUCTION` | Domyślna instrukcja określająca, co dron ma robić, jeżeli działa, ale nie otrzymał jeszcze instrukcji użytkownika. |
| `USER_INSTRUCTION` | Instrukcja użytkownika, która po podaniu nadpisuje `GENERAL_INSTRUCTION`. |
| `USER_PROMPT` | Instrukcja użytkownika przekazywana podczas misji. Pozwala modyfikować sposób wykonania misji, ale nie nadpisuje instrukcji nadrzędnej. |

### 3.2. Sterowanie przez GUI połączone z LLM

Alternatywną ścieżką wydawania poleceń jest GUI stacji naziemnej. Ta ścieżka zawsze pozostaje połączona z LLM.

Operator może na mapie:

- Zaznaczyć punkt docelowy lotu.
- Wyznaczyć zygzak do oblotu i obserwacji.
- Wyznaczyć kilka checkpointów do odwiedzenia.

Tak zdefiniowane polecenia trafiają bezpośrednio do układu sterującego dronem, np. autopilota lub komputera sterującego, z pominięciem wyborów dokonywanych przez model lub metodę NLP.

Jednocześnie model NLP otrzymuje nadpisaną `GENERAL_INSTRUCTION`, opisującą kontekst działań wynikających z GUI. Kontekst ten może być pomocny, jeżeli dron napotka trudność w wykonaniu misji.

### 3.3. Reprezentacja i przesyłanie poleceń NLP

Rozważane są następujące reprezentacje:

| Reprezentacja | Założenie lub motywacja |
| --- | --- |
| Embeddingi, czyli wektory | Punktem wyjścia jest założenie, że wektor będzie łatwiej przesłać. |
| JSON z wektoryzacją pól | Alternatywa wynikająca z obawy o utratę informacji przy reprezentacji wektorowej. Polecenie operatora jest zamieniane przez model System One na JSON, a wartości jego pól są wektoryzowane. |

Ostateczna postać reprezentacji pozostaje do ustalenia. Założenie o łatwiejszym przesyłaniu wektorów i możliwość utraty informacji nie są tutaj traktowane jako potwierdzone wyniki.

### 3.4. Środowisko i komponenty stacji

- Zakładana moc obliczeniowa odpowiada w miarę szybkiemu laptopowi z kartą graficzną.
- Dopuszczone jest uruchomienie stacji na mocniejszym serwerze, umożliwiającym użycie mocniejszych modeli.
- W wariancie serwerowym laptop łączy się ze stacją przez aplikację webową.

Przewidziane komponenty:

- Model LLM.
- Model System One, np. rozwiązanie określone w założeniach jako „JEV od TypeSafe AI”.
- Gotowe moduły tradycyjnej naziemnej stacji kontroli.

Dodatkowe moduły tradycyjnej stacji kontroli nie będą implementowane w ramach projektu — mają zostać wykorzystane jako gotowe rozwiązania.

## 4. Dron

Na ten moment rozważane są dwie konfiguracje drona:

- Dron w architekturze klasycznej.
- Quadkopter, np. taki jak drony DJI.

### 4.1. Odbierane polecenia

Dron otrzymuje:

- Słownik wektorów reprezentujących polecenia.
- Oddzielny słownik z predefiniowanym poleceniem utworzonym przez GUI, jeżeli wykorzystano tę ścieżkę.

Polecenie z GUI może określać np. lot do punktu A, obserwację po zygzaku lub czas pracy.

### 4.2. Wykonywanie i modyfikacja misji

Dron wykonuje misję i może:

- Zmienić jej przebieg.
- Zmienić sposób jej wykonania.
- Przerwać ją.

Takie działanie następuje w odpowiedzi na konkretną sytuację wpływającą na warunki wykonania misji.

### 4.3. Czujniki

Dron może posiadać różne zestawy czujników. Nie wszystkie czujniki muszą być obecne.

Rozważane źródła informacji:

- LiDAR.
- Kamera kolorowa.
- Czujnik laserowy.
- Czujnik Dopplera.
- Inne czujniki popularne w rozważanych typach i konfiguracjach dronów.

Czujniki dostarczają informacji o stanie otoczenia. Ich dane są przekształcane do reprezentacji liczbowej czytelnej dla modelu obliczeniowego. Określenie „model obliczeniowy” jest tutaj ogólne i nie oznacza konkretnego modelu AI.

Prawdopodobnie każdy rodzaj czujnika będzie przetwarzany inaczej. Wyniki przetwarzania należy objąć abstrakcją ogólnego źródła informacji o wymaganej postaci danych i metodach.

Informacje z czujników powinny być możliwe do sztucznego zasymulowania na potrzeby testowania środowiska.

### 4.4. Informacja o celu lub obserwowanym obiekcie

Przewidziane są dwa przypadki:

- Stacja naziemna informuje o obecności celu; dron ma go odnaleźć i kierować się na niego.
- Dron sam wyszukuje cel lub na bieżąco interpretuje informacje o otoczeniu.

W drugim przypadku rozważane są detekcja obiektów przez YOLO oraz alternatywa oparta na lekkim modelu wizyjno-językowym.

### 4.5. Percepcja oparta na YOLO

YOLO stanowi podstawowe rozważane rozwiązanie do wykrywania obiektów w otoczeniu.

Rozważane są dwa sposoby dopasowania obiektu do polecenia użytkownika:

| Wariant | Opis | Wskazane właściwości |
| --- | --- | --- |
| Dopasowanie embeddingów | Wykryty obiekt jest reprezentowany przez embedding i porównywany z wektorem opisującym obiekt wskazany przez użytkownika w poleceniu JSON. | Dopasowanie oparte na reprezentacji wektorowej. |
| Dopasowanie do klasy YOLO | Już na stacji naziemnej poszukiwany lub obserwowany obiekt jest przypisywany do jednej z rozpoznawanych klas YOLO. | Łatwiejsze i szybsze, ale mniej elastyczne. |

### 4.6. Alternatywa wizyjno-językowa

Alternatywą jest bardzo lekki model wizyjno-językowy, określony w założeniach jako „VLLM”, zwracający embedding informacji o otoczeniu.

Zakładane możliwości i ograniczenia:

- Nie należy zakładać możliwości bezpośredniego porównywania embeddingów pochodzących z różnych modeli. W założeniach wskazano użycie tej samej rodziny modeli jako możliwy warunek zgodności.
- Embedding informacji o otoczeniu może służyć jako wejście do modelu decyzyjnego sterującego zachowaniem drona.

Konkretny model nie został wybrany.

### 4.7. Wykonywanie poleceń lotu

Początkowo dronem steruje autopilot. Projekt nie ingeruje na tym etapie w macierze sterowania — przekazuje polecenia do autopilota.

Autopilot musi być objęty abstrakcją od początku, ponieważ:

- W pierwszym środowisku dron będzie symulowany i nie będzie rzeczywistego autopilota.
- W przyszłości dopuszczona jest zamiana autopilota na model wpływający na macierze sterowania.
- Różne przeznaczenia i konfiguracje drona mogą wymagać odmiennego sposobu lotu; w założeniach wskazano przykłady drona bojowego i transportowego.

### 4.8. Ograniczenia sprzętowe

Zakładany górny poziom sprzętu pokładowego określono jako „Jetson Nano 16 GB”. Pożądane jest również działanie na urządzeniu z 8 GB pamięci.

Dokładne oznaczenie urządzenia nie zostało doprecyzowane.

## 5. Środowisko symulacyjne i trening

Środowisko powinno umożliwiać symulację misji w konfiguracji klasycznej i quadkoptera oraz obserwację ich przebiegu.

Na obecnym etapie do symulacji dronów wykorzystujemy gotową bibliotekę zawierającą modele ich ruchu. Do symulowania działania autopilota również chcemy wykorzystać gotową bibliotekę, jeżeli takie rozwiązanie jest dostępne. Konkretne biblioteki nie zostały jeszcze wybrane.

Symulacja czujników ma dostarczać informacji zbliżonych do rzeczywistych, bez zbędnej komplikacji. Abstrakcje źródeł danych mają umożliwić późniejszą zamianę czujników symulowanych na rzeczywiste.

Do treningu należy wykorzystać gotową architekturę modelu decyzyjnego. Trening powinien uwzględniać wiele implementowanych modułów systemu, a nie wyłącznie sam model decyzyjny.

Nie wskazano jeszcze konkretnego symulatora ani szczegółowej konfiguracji treningu.

## 6. Model decyzyjny

Wybór modelu decyzyjnego pozostaje najtrudniejszą otwartą decyzją.

Preferowane jest rozwiązanie w stylu MuZero, ale nie przesądzono, że samo MuZero będzie odpowiednim wyborem.

Dopuszczone są inne modele, jeżeli umożliwiają:

- Elastyczne definiowanie przestrzeni działania bez jej wcześniejszego predefiniowania.
- Pracę w czasie ciągłym.

Sposób realizacji tych wymagań i konkretna architektura pozostają do ustalenia.

## 7. Dobór narzędzi

### 7.1. Licencje

Podstawowym kryterium jest możliwość darmowego użycia narzędzia w zastosowaniach komercyjnych.

Wskazany wyjątek dotyczy YOLO. Planowane jest przetestowanie dwóch modułów objętych wspólną abstrakcją:

- Darmowego wariantu YOLO.
- YOLO od Ultralytics.

Konkretny darmowy wariant nie został wskazany.

### 7.2. Gotowe rozwiązania

W miarę możliwości należy korzystać z gotowych narzędzi, jeżeli:

- Ich repozytoria są nadal utrzymywane.
- Działają z dość świeżą wersją Pythona.
- Liczba gwiazdek i współtwórców na GitHubie pozwala przypuszczać, że pakiet jest stabilny.

Każde narzędzie należy opakować w abstrakcję odpowiadającą pełnionej funkcji, aby można było łatwo zastąpić je innym.

## 8. Implementacja i organizacja repozytorium

### 8.1. Język i zarządzanie zależnościami

- Pierwszy prototyp powstaje w całości w Pythonie.
- Wymagana wersja: Python `>=3.12`.
- Pakietami i środowiskiem zarządza `uv`.
- Projekt ma być poprawnie pakowaną paczką Pythona.

Grupy zależności:

| Grupa | Zakres |
| --- | --- |
| `basic` | Inferencja i praca wokół inferencji. |
| `dev` | Trening i testowanie. |

### 8.2. Organizacja kodu

- Priorytetem jest poprawność implementacji.
- Logika poszczególnych modułów jest rozdzielona.
- Obowiązuje architektura heksagonalna: centralna logika każdego modułu jest oddzielona od konkretnych integracji.
- Logika specyficzna dla odrębnych funkcjonalności znajduje się w oddzielnych plikach.
- Narzędzia i komponenty podlegające wymianie mają odpowiednie abstrakcje.

### 8.3. GitHub Actions

Repozytorium ma zawierać automatyzację:

- Testowania.
- Lintingu.

Pozostałe wymagania dotyczące CI nie zostały określone w pierwotnych założeniach. Zasady pracy i kontroli jakości rozwija `AGENTS.md`.

### 8.4. Instrukcje dla agentów

`AGENTS.md` ma:

- Odnosić się do struktury repozytorium i ogólnego celu projektu.
- Linkować dokumenty z dokładniejszymi opisami.
- Opisywać zasady jakości kodowania i sposób pracy.
- Wymagać test driven development.
- Ograniczać ilość produkowanego kodu bez ograniczania funkcjonalności.

## 9. Nierozstrzygnięte elementy

Poniższe kwestie wynikają z alternatyw lub niedoprecyzowanych punktów powyższych założeń:

- Ostateczna reprezentacja i format przesyłania poleceń NLP.
- Konkretny LLM i model System One.
- Konkretny model decyzyjny i sposób realizacji wymagań dotyczących przestrzeni działania oraz czasu ciągłego.
- Konkretny symulator i szczegóły treningu.
- Konkretny darmowy wariant YOLO oraz ewentualny lekki model wizyjno-językowy.
- Dokładne urządzenie pokładowe.
- Szczegółowe zestawy czujników dla poszczególnych konfiguracji drona.
- Dalsze elementy środowiska developerskiego, CI i zasad pracy, które w pierwotnym opisie pozostawiono jako niepełną listę.

## 10. Plan architektury i granice modułów

Jednostką ponownego użycia będzie **epizod scenariusza**. Ten sam opis świata i ten sam przebieg w czasie mają służyć do uruchomienia przykładu z CLI, sprawdzenia zmiany misji, zebrania danych i porównania dwóch modeli. Każdy z tych odbiorców potrzebuje innych wyników. CLI zapisuje trasę, operator ogląda postęp, a eksperyment odczytuje kolejne obserwacje i wynik zadania. Wszystkie trzy ścieżki powinny korzystać z jednej implementacji upływu czasu i reguł misji.

Rozdziały 10–15 są propozycją organizacji prac. Nazwy nowych plików określają miejsce odpowiedzialności, a nazwy typów opisują proponowane kontrakty. Plik powstaje wraz z jego pierwszym działającym przypadkiem użycia. Wybory wymienione w rozdziale 9 pozostają otwarte.

### 10.1. Punkt wyjścia

Obecna symulacja już przyjmuje listę pojazdów z YAML. Dwa pojazdy są właściwością przykładu. Każdy ma osobny autopilot i trasę, a `Simulation.step(dt)` przesuwa je we wspólnym czasie. `Flight.replace_mission()` i `Flight.cancel()` pozwalają zmienić misję w Pythonie. Obecne zachowanie i ograniczenia opisuje [dokumentacja symulacji](docs/simulation.md).

Ograniczenie dla dalszych prac leży w sposobie prowadzenia przebiegu. `run(config, output)` tworzy pojazdy, wykonuje całą pętlę i zapisuje pliki. Konfiguracja odtwarza stan początkowy i trasy, ale nie opisuje zmian w czasie. Stan zwracany przez adapter dynamiki jest prawdą symulatora. Model otrzymujący go bezpośrednio miałby dokładniejszą wiedzę niż model korzystający z czujników. Z tego wynikają trzy pierwsze zadania: wydzielenie epizodu pracującego w pamięci, wprowadzenie zdarzeń scenariusza oraz jawne zbudowanie obserwacji z pomiarów.

### 10.2. Docelowe drzewo repozytorium

Drzewo pokazuje pliki istotne dla architektury. Obecne punkty wejścia i adaptery symulacji zachowują swoje miejsce. Pozostałe moduły opisują plan. Nazwy profili YAML są przykładami podziału konfiguracji.

```text
.
├── PROJECT.md                         wymagania i plan rozwoju
├── AGENTS.md                          zasady pracy i utrzymania kontraktów
├── README.md                          instrukcje dla dostępnych funkcji
├── pyproject.toml / uv.lock           pakowanie, grupy zależności i ich wersje
├── MANIFEST.in                        pliki dodatkowe w dystrybucji źródłowej
├── configs/
│   ├── simulation/
│   │   ├── sensors/                   profile symulowanych czujników
│   │   └── scenarios/                 obsada, trasy i harmonogram przebiegu
│   │       ├── default.yaml           domyślny przykład lotu dwóch pojazdów
│   │       ├── route_change.yaml      zaplanowana zmiana trasy
│   │       └── mission_cancellation.yaml  anulowanie misji i przerwa w pomiarach
│   ├── vehicles/quadrotor.yaml        typ pojazdu, model dynamiki i możliwości
│   ├── sensors/survey.yaml            wyposażenie, częstotliwości, opóźnienia
│   ├── ground_station/local.yaml      adapter wejścia operatora i interpretacji
│   ├── perception/default.yaml        wersje modeli i ich wejścia
│   ├── decision/default.yaml          wariant inferencji i budżet obliczeń
│   └── training/baseline.yaml         zbiory scenariuszy, ziarna, warunki oceny
├── src/uav_onboard_planner/
│   ├── mission/
│   │   ├── instructions.py            hierarchia instrukcji i aktualny kontekst
│   │   ├── commands.py                typowane polecenia i ich pochodzenie
│   │   └── execution.py               przebieg misji, zmiana trasy, anulowanie
│   ├── ground_station/
│   │   ├── operator.py                przyjęcie polecenia GUI lub tekstu
│   │   ├── interpretation.py          port interpretacji tekstu i System One
│   │   └── adapters/                  połączenie z gotową stacją, GUI i LLM
│   ├── communication/
│   │   ├── messages.py                wersja wiadomości, adresat, identyfikatory
│   │   └── adapters/                  kodowanie i transport wiadomości
│   ├── sensors/
│   │   ├── measurements.py            próbki, czas pomiaru i dostępność źródła
│   │   └── adapters/                  odczyt i kalibracja konkretnego urządzenia
│   ├── perception/
│   │   ├── observations.py            obserwacje i opis przestrzeni embeddingu
│   │   ├── processing.py              pomiary → obserwacje dla odbiorców
│   │   └── adapters/                  detektor lub model wizyjno-językowy
│   ├── decision/
│   │   ├── policy.py                  wejście, dostępne działania, wynik decyzji
│   │   └── adapters/                  wykonanie wybranego modelu inferencyjnego
│   ├── onboard/
│   │   ├── cycle.py                   obsługa polecenia, pomiarów i decyzji
│   │   ├── flight.py                  port wykonania polecenia i potwierdzenie
│   │   └── adapters/                  przyszła integracja autopilota sprzętowego
│   ├── simulation/
│   │   ├── config.py                  walidacja konfiguracji uruchomienia
│   │   ├── scenario.py                definicje pojazdów, zdarzeń i końca epizodu
│   │   ├── episode.py                 zegar, stan przebiegu, reset i krok
│   │   ├── sensors.py                 pomiary syntetyczne ze stanu świata
│   │   ├── contracts.py / mission.py   obecne kontrakty i logika pojedynczego lotu
│   │   ├── adapters/                  rotorpy.py i jsbsim.py, dynamika pojazdów
│   │   ├── runner.py / __main__.py     złożenie zależności i uruchomienie przez CLI
│   │   ├── recording.py               zapis próbek i metadanych epizodu
│   │   └── visualization.py           prezentacja zarejestrowanego przebiegu
│   └── training/
│       ├── environment.py             przekład kroku epizodu na próbkę treningową
│       ├── experiment.py              trening, wersja danych, zapis artefaktów
│       └── evaluation.py              porównanie modeli na wydzielonych scenariuszach
├── tests/
│   ├── simulation/                    obecne testy lotów, konfiguracji i adapterów
│   ├── mission/ / onboard/            reguły poleceń i wykonania
│   ├── sensors/ / perception/         kontrakty pomiarów i obserwacji
│   ├── decision/ / training/          zgodność wejść treningu i inferencji
│   └── integration/                   scenariusze przekraczające granice modułów
├── docs/                              opis aktualnej implementacji według AGENTS.md
└── .github/workflows/                 CI oraz kontrola tytułów PR
```

Port należy do modułu, który potrzebuje danej zdolności. Przykładowo pokład zna operację wykonania polecenia, a adapter symulacji tłumaczy ją na wywołanie konkretnego autopilota. Kierunek importów biegnie od adaptera do kontraktu. CLI, aplikacja stacji i proces treningowy składają własne zestawy zależności. Domena misji nie importuje YAML, GUI, bibliotek modeli ani silnika dynamiki. Wspólny kod wydzielamy wtedy, gdy ma dwóch konkretnych odbiorców, np. wykonawcę misji w symulacji i na pokładzie. Moduły mogą początkowo działać w jednym procesie.

## 11. Scenariusz, epizod i czas

**Scenariusz** jest opisem wartości początkowych i zaplanowanych zmian. Zawiera identyfikator i wersję schematu, układ odniesienia, profile pojazdów i sensorów, role pojazdów, misje początkowe, harmonogram oraz limit czasu. Pojazd oceniany i pojazdy ruchu tła korzystają z tej samej dynamiki. Rola określa, kto dostarcza polecenia i dla którego pojazdu liczymy wynik. Liczba pojazdów nie zmienia interfejsu epizodu.

**Epizod** jest jednym wykonaniem scenariusza. Posiada zegar, instancje backendów, aktualne misje, kolejkę zdarzeń i bufory pomiarów. Reset odtwarza stan początkowy z wybranego scenariusza i ziarna, czyści historię, opóźnione próbki i stan kontrolerów. Utworzenie dwóch epizodów z tego samego opisu daje niezależne obiekty. Profil odczytany z YAML pozostaje niezmienny przez cały przebieg.

| Proponowana operacja | Odpowiedzialność i obserwowalny wynik |
| --- | --- |
| Wczytanie scenariusza | Walidacja typów, skończonych liczb, unikalnych nazw, jednostek, odniesień do pojazdów, zgodności backendu z modelem oraz zakresów czasu przed utworzeniem silnika. Błąd wskazuje plik i pole. |
| Rozpoczęcie lub reset | Stan w chwili zero i pierwsze dostępne obserwacje. Brak pierwszej próbki jest dopuszczalnym wynikiem. |
| Dostarczenie zmiany | Polecenie identyfikuje pojazd, misję, źródło i czas skuteczności. Przyjęcie lub odrzucenie ma przyczynę. Powtórzenie identycznego komunikatu nie uruchamia misji drugi raz. |
| Przesunięcie do kolejnej chwili decyzji | Silnik wykonuje potrzebną liczbę kroków dynamiki, obsługuje zdarzenia i udostępnia obserwacje dostępne do tej chwili. Wynik zawiera rzeczywisty odstęp czasu. |
| Zakończenie | Oddzielny status misji każdego pojazdu i przyczyna zamknięcia epizodu, np. spełnienie warunku scenariusza, limit czasu, przerwanie przez operatora lub błąd integracji. |

Proponowana kolejność na granicy czasu to dostarczenie oczekujących poleceń i gotowych pomiarów, rozstrzygnięcie poleceń zgodnie z rozdziałem 3, wykonanie decyzji, a następnie integracja do kolejnego zdarzenia. Pomiar ze stanu osiągniętego na końcu kroku dostaje czas tego stanu. Do odbiorcy trafia po upływie skonfigurowanego opóźnienia. Wszystkie pojazdy są oceniane względem tej samej zatwierdzonej chwili. Częstotliwość fizyki, odczytu czujnika, decyzji i zapisu mogą się różnić. Zmiana częstotliwości wykresu nie powinna zmieniać trajektorii.

Zdarzenie scenariusza opisuje **co i kiedy** dostarczyć do wskazanego modułu. Zmiana trasy przechodzi przez ten sam przypadek użycia co zmiana operatora. Awaria sensora zmienia dostępność pomiarów, bez bezpośredniego przestawiania stanu modelu decyzyjnego. Dla zdarzeń jednoczesnych należy określić stabilną kolejność i sprawdzić konflikty przy wczytywaniu. Kolejność wpisów w YAML nie może zmienić pierwszeństwa GUI. Po częściowej awarii kroku epizod przechodzi w stan błędu z czasem ostatniego pełnego kroku. Odbiorcy dostają wyłącznie kompletne próbki, a ponowne wykonanie zaczyna się od resetu.

**Scenariusz odbiorczy.** Quadkopter wykonuje przegląd obszaru, a stałopłat przelatuje własną trasą. W 12. sekundzie operator zmienia ostatni punkt przeglądu. Od 18. do 21. sekundy kamera nie dostarcza klatek. W 25. sekundzie operator anuluje przegląd. Oczekiwane wyniki to zmiana jednej misji, zachowanie trasy stałopłata, trzy sekundy jawnej niedostępności kamery i anulowanie misji quadkoptera przy dalszym działaniu świata. Ten sam przypadek powinien dać się wykonać z CLI, krokowo w teście oraz w procesie ewaluacji bez zapisu na dysk.

## 12. Kontrakty między stacją, pokładem i symulatorem

| Dane | Producent → odbiorca | Co kontrakt musi rozstrzygać |
| --- | --- | --- |
| Kontekst instrukcji | Stacja → interpretacja i pokład | Osobne pola dla czterech poziomów z §3.1, identyfikator wersji kontekstu oraz źródło zmiany. Brak instrukcji użytkownika oznacza użycie instrukcji domyślnej. |
| Polecenie GUI | Adapter mapy → wykonawca misji | Adresat, punkt/trasa/obszar, odniesienie przestrzenne i ograniczenie czasowe. Równoległa aktualizacja kontekstu NLP niesie ten sam identyfikator. Wykonanie GUI omija wybór modelu, zgodnie z §3.2. |
| Komunikat NLP | Interpretacja → transport → pokład | Jawne znaczenie pól, wersja reprezentacji, walidacja po obu stronach. Kodowanie wektorowe i JSON pozostają wariantami do porównania. Rozmiar oraz czas kodowania należy zmierzyć na tych samych poleceniach. |
| Stan świata | Dynamika → symulowane sensory, rejestrator i ewaluacja | Identyfikator pojazdu, czas symulacji w sekundach, pozycja ENU w metrach i prędkość ENU w m/s. Każdy kolejny układ wymaga jawnego początku, orientacji i konwersji w adapterze. |
| Pomiar | Sensor symulowany lub sprzętowy → percepcja | Typ pomiaru, jednostki, układ sensora, parametry kalibracji, czas pomiaru i odbioru. Profil wyposażenia rozstrzyga brak urządzenia. Zainstalowane urządzenie może nie mieć nowej próbki albo zgłosić błąd. |
| Obserwacja | Percepcja → model decyzyjny | Czas źródłowy, dostępność, źródło i typ cech. Pusta lista detekcji z poprawnej klatki różni się od braku klatki. Wektor ma identyfikator i wersję modelu, wymiar i identyfikator przestrzeni. |
| Decyzja i wykonanie | Model → logika misji → port wykonania | Propozycja działania odnosi się do konkretnej misji, chwili i możliwości pojazdu. Wykonawca sprawdza jej dopuszczalność i zwraca rezultat. Przyjęcie polecenia, rozpoczęcie oraz fizyczne osiągnięcie punktu to trzy różne zdarzenia. |

Logika utrzymywania lub zmiany instrukcji należy do domeny misji. Adapter GUI tłumaczy interakcję z mapą, adapter LLM tłumaczy tekst, transport przenosi wersjonowany komunikat. Każdy może zgłosić błąd na swojej granicy. Utrata łączności, przeterminowana zmiana lub nieobsługiwana wersja polecenia muszą dawać rozpoznawalny wynik. Konkretne czasy ważności i reakcje operacyjne wymagają zatwierdzenia w specyfikacji misji.

Obecny port `Autopilot` łączy polecenie z operacją `step(dt)`. Przy dodaniu drugiego środowiska trzeba rozdzielić te obowiązki. Pokład wysyła polecenia i odbiera potwierdzenia. Wyłącznie symulator przesuwa czas fizyki. Sprzęt dostarcza pomiary przez port sensora. Czas symulacji i znaczniki urządzenia wymagają jawnej podstawy czasu przed łączeniem próbek. Ukończenie trasy, anulowanie i zachowanie charakterystyczne dla danego typu pojazdu pozostają częścią testowanego kontraktu.

## 13. Trening, ewaluacja i odtwarzalność

Adapter treningowy dostaje fabrykę epizodów oraz konfigurację zadania. Na początku wybiera scenariusz i ziarno z zestawu treningowego. W każdym kroku dostarcza bieżący kontekst i obserwację do polityki, przekazuje zaakceptowaną decyzję do wykonawcy i odczytuje następny wynik. Jedna próbka zawiera identyfikatory epizodu i pojazdu, obserwację, dostępne działania, decyzję, wynik wykonania, następną obserwację, upływ czasu i przyczynę zakończenia. Definicja nagrody i metryk należy do zadania treningowego. Dzięki temu ten sam epizod może służyć do demonstracji i porównania modeli bez zmiany fizyki.

Oddzielne wejście dla oceny pozwala porównać wynik misji z prawdą symulatora. Polityka podczas treningu i inferencji dostaje wyłącznie informacje dostępne dla danego pojazdu przed chwilą decyzji. Dotyczy to także kolejnych pozycji ruchu tła i przyszłych poleceń z harmonogramu. Definicje wejścia modelu, kolejność cech, normalizacja i wersja reprezentacji muszą być współdzielone przez trening i inferencję. Ładowanie artefaktu z niezgodnym schematem kończy się jawnym błędem.

Do pierwszego porównania wystarczy ten sam zestaw misji inspekcyjnych z dostępną kamerą, z opóźnieniem klatek i po anulowaniu misji. Porównujemy ukończenie zadania, respektowanie zmiany operatora, czas reakcji, opóźnienie inferencji i szczytowe zużycie pamięci. Zestawy treningowy i ewaluacyjny rozdzielamy po scenariuszach, zapisując również ziarna. Przy porównaniu wariantów zachowujemy tę samą obsadę i warunki początkowe. Wyniki na laptopie, serwerze i urządzeniu pokładowym raportujemy oddzielnie.

Manifest przebiegu powinien rozszerzyć obecny `run.json` o wersję schematu, rozwiniętą konfigurację profili, wersje silników, identyfikatory modeli i wag, ziarna poszczególnych źródeł losowości, powód zakończenia i wersję metryk. Odtworzenie zdarzeń operatora wymaga zapisu zarówno czasu dostarczenia, jak i treści przyjętej zmiany. Powtarzalność w tej samej konfiguracji weryfikujemy testem, a tolerancje porównań między platformami ustalamy dla konkretnego backendu. Duże nagrania, dane i wagi pozostają poza repozytorium.

## 14. Proponowany stos technologiczny

| Obszar | Punkt wyjścia | Warunek rozszerzenia lub wyboru |
| --- | --- | --- |
| Rdzeń i kontrakty | Python ≥3.12, typowane dataclasses i małe porty Protocol. Biblioteka standardowa wystarcza do harmonogramu, identyfikatorów i zapisu CSV/JSON. | Zewnętrzny framework dopiero przy konkretnej potrzebie odbiorcy. |
| Konfiguracja i dystrybucja | Obecne PyYAML na brzegu aplikacji, uv, pyproject.toml, uv.lock i setuptools. | Każdy profil ma właściciela walidacji. Stary przykład YAML pozostaje testem kompatybilności po dodaniu scenariuszy. |
| Dynamika i prezentacja | Obecne RotorPy dla quadkopterów, JSBSim dla modelu referencyjnego stałopłata, NumPy w adapterach i Matplotlib dla trajektorii. | Dokładność konkretnego modelu wymaga kalibracji. Zmiana backendu przechodzi te same testy czasu, jednostek, zmiany i zakończenia misji. |
| Stacja i transport | Najpierw gotowa stacja zgodnie z §3.4 i adapter w pamięci do testów kontraktowych. | Integrację webową, konkretny transport, model System One i LLM wybieramy po próbie z docelową stacją i pomiarze opóźnienia. |
| Percepcja i inferencja | Osobne adaptery dla wariantów z §4.5–4.6. Wspólne wejścia i metryki pozwalają porównać wyniki. | Wybór wymaga testu jakości, zgodności reprezentacji i budżetu urządzenia. Wariant Ultralytics wymaga osobnej decyzji licencyjnej. |
| Trening i polityka | Pierwszym odbiorcą API epizodu będzie testowa polityka deterministyczna. Następnie adapter gotowej architektury zgodnej z §6. | Próba musi wykazać obsługę czasu działania i możliwości pojazdu bez utrwalania zamkniętej listy akcji w całym systemie. MuZero pozostaje kandydatem. |
| Kontrola jakości | Obecne pytest, Ruff, mypy i GitHub Actions. Budowa wheel/sdist i import po instalacji. | Do CI dodajemy małe testy kontraktów na CPU. Trening, ewaluację jakości i pomiary sprzętowe uruchamiamy osobno. |

Do grupy `basic` trafi wyłącznie oprogramowanie wymagane do uruchomienia wybranej inferencji. Symulacja, optymalizator, ewaluacja oraz narzędzia testowe pozostają w `dev`. Import rdzenia nie pobiera wag, nie otwiera połączeń i nie inicjuje GPU. Przed dodaniem nowej biblioteki dokumentujemy zgodność z Pythonem i urządzeniem, aktywność projektu oraz oddzielne warunki użycia kodu, parametrów modelu, wag i danych. Dotychczasowe zależności i kontrole opisują [docs/simulation.md](docs/simulation.md) i [docs/tooling.md](docs/tooling.md).

## 15. Kolejność realizacji i kryteria odbioru

| Etap | Najmniejsza kompletna zmiana | Warunek odbioru |
| --- | --- | --- |
| 1. Epizod w pamięci | Wydzielić z runnera sterowanie czasem i rejestrowanie. Zachować istniejącą komendę, konfigurację i formaty wyników. | Ten sam przykład daje zgodny przebieg z CLI i przy ręcznym krokowaniu. Epizod bez rejestratora nie tworzy plików. |
| 2. Predefiniowany scenariusz | Dodać role pojazdów, zdarzenia czasowe, reset i przyczynę końca. Najpierw zastąpienie i anulowanie trasy. | Po resecie dwa niezależne wykonania odtwarzają zdarzenia w tej samej kolejności. Zmiana misji jednego drona nie nadpisuje misji drugiego. |
| 3. Obserwacje | Podłączyć jeden typ symulowanego sensora i konsumenta pomiarów, potem kolejne profile. | Test rozróżnia brak wyposażenia, opóźnioną próbkę, błąd i poprawny pomiar bez obserwacji. Polityka nie otrzymuje danych z przyszłości. |
| 4. Polecenia i pokład | Wprowadzić typowany komunikat, port wykonania i cykl pokładowy. Sprawdzić najpierw z atrapą stacji, następnie z wybraną integracją. | Zmiana GUI działa przy niedostępnym modelu, kontekst NLP odzwierciedla tę samą zmianę, a USER_PROMPT zachowuje ograniczenia instrukcji nadrzędnej. |
| 5. Eksperyment | Uruchomić trening i ocenę z jednym adapterem środowiska i odrębnymi zestawami scenariuszy. | Model i punkt odniesienia dostają te same obserwacje. Raport podaje warunki, wersje, metryki i ograniczenia wyników. |
| 6. Inferencja na sprzęcie | Po ustaleniu urządzenia uruchomić artefakt inferencyjny z grupą basic oraz odtwarzanym strumieniem pomiarów. Następnie podłączyć adapter rzeczywistego źródła. | Sprawdzić kontrakt danych oraz zmierzyć pamięć i opóźnienie na wskazanym urządzeniu, osobno dla rozważanych konfiguracji 8 i 16 GB. |

Każdy etap zaczyna się od testu widocznego zachowania. Przy zmianie kontraktu w jednej zmianie aktualizujemy producenta, odbiorców, testy i opis danych. Szczegóły wdrożonych rozwiązań trafiają do dokumentu obszarowego zgodnie z mapą w [AGENTS.md](AGENTS.md). Decyzje o sprzęcie, modelach, obsługiwanych sensorach i formacie poleceń z rozdziału 9 wymagają osobnego uzasadnienia przed wdrożeniem odpowiedniego etapu.
