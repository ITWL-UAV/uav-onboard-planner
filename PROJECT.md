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
