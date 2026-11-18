# AGENTS.md

## Cel i zakres

Projekt rozwija narzędzie do symulacji, treningu i wykonywania misji drona na podstawie poleceń operatora oraz informacji z dostępnych czujników. Obejmuje stację naziemną, pokładową logikę decyzyjną i integrację z symulatorem. Pierwszy prototyp powstaje w Pythonie; późniejsze przeniesienie inferencji do Rusta pozostaje poza bieżącym zakresem.

Ten plik opisuje sposób pracy. Szczegółów projektu nie należy tutaj powielać.

## Dokumentacja projektu

Docelowy podział dokumentacji poniżej jest mapą odnośników. Pliki należy dodawać wraz z opracowaniem danego obszaru; sam wpis nie oznacza, że plik już istnieje.

| Plik | Zakres |
| --- | --- |
| [README.md](README.md) | Instalacja, uruchomienie, dostępne funkcje i aktualna struktura repozytorium. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Zasady kontrybucji, format komunikatów commitów i tytułów pull requestów oraz sposób ich weryfikacji w CI. |
| [docs/project.md](docs/project.md) | Cel, zakres, wymagania, ograniczenia i etapy realizacji. |
| [docs/architecture.md](docs/architecture.md) | Moduły, kierunki zależności, porty, adaptery i przepływ danych. |
| [docs/mission.md](docs/mission.md) | Hierarchia instrukcji, polecenia GUI, kontrakty komunikacji i cykl życia misji. |
| [docs/simulation.md](docs/simulation.md) | Konfiguracje dronów, czujniki, scenariusze i uproszczenia symulacji. |
| [docs/models.md](docs/models.md) | Percepcja, reprezentacje danych, model decyzyjny, trening i ewaluacja. |
| [docs/tooling.md](docs/tooling.md) | Zależności, licencje, środowiska, polecenia developerskie i CI. |

Przed pracą przeczytaj dokumentację dotyczącą zmienianego obszaru. Jeśli jej brakuje, opieraj się na zatwierdzonych wymaganiach i istniejącym kodzie. Brak dokumentu nie oznacza zgody na samodzielne rozstrzygnięcie otwartej decyzji projektowej.

## Sposób pracy

- Przed przygotowaniem commita lub utworzeniem, aktualizacją albo scaleniem pull requesta przeczytaj [CONTRIBUTING.md](CONTRIBUTING.md). Sprawdź zgodność nowych komunikatów commitów i tytułu PR z Conventional Commits. Przy squash merge użyj tytułu PR jako tematu commita.

- Przed zmianami znajdź i przeczytaj właściwe `AGENTS.md` oraz `CLAUDE.md`, także w katalogach nadrzędnych i w zmienianym poddrzewie.
- Najpierw poznaj istniejącą implementację, jej wywołania, kontrakty i testy. Korzystaj z obecnych rozwiązań, zanim dodasz nowe.
- Realizuj małe, kompletne zmiany odpowiadające konkretnemu wymaganiu. Nie łącz ich z niepowiązanym refaktoringiem.
- Rozwiązuj rutynowe szczegóły samodzielnie. Pytaj, gdy brak informacji zmienia zachowanie systemu, publiczny kontrakt lub zakres zadania.
- Nie traktuj propozycji, hipotezy ani przykładu jako zatwierdzonej decyzji. Otwarte wybory zapisuj wyraźnie w odpowiedniej dokumentacji.
- Zachowuj niezwiązane zmiany użytkownika. Nie resetuj repozytorium i nie usuwaj cudzej pracy.
- Po zmianie podaj wynik, wykonane sprawdzenia i istotne ograniczenia. Nie deklaruj uruchomienia testów, których nie wykonano.

## Prostota i jakość kodu

- Ograniczaj ilość kodu bez ograniczania wymaganej funkcjonalności. Preferuj rozwiązania czytelne i łatwe do usunięcia lub zastąpienia.
- Najpierw sprawdź bibliotekę standardową, istniejący kod i obecne zależności. Nową zależność dodawaj dla konkretnej potrzeby.
- Nie twórz infrastruktury na zapas, ogólnych frameworków ani konfiguracji dla hipotetycznych przypadków.
- Oddzielaj odpowiedzialności. Odrębne funkcjonalności umieszczaj w oddzielnych plikach, ale nie rozbijaj spójnej logiki na sztuczne warstwy.
- Używaj nazw opisujących znaczenie danych i operacji. Unikaj zbiorczych modułów `utils.py`, jeśli kod ma konkretną odpowiedzialność.
- Stosuj adnotacje typów w publicznych interfejsach i kontraktach. Nie ukrywaj niejasnego modelu danych za `Any` ani nieopisanym słownikiem.
- Komentarze mają wyjaśniać powód, założenie lub ograniczenie. Nie powtarzaj w nich kodu.
- Waliduj dane na granicach systemu. Obsługuj oczekiwane błędy jawnie; nie tłum wyjątków i nie zamieniaj awarii w pozorny sukces.
- Nie dodawaj sekretów, dużych zbiorów danych, wag modeli ani wyników eksperymentów do repozytorium.

## Architektura i kontrakty

- Stosuj architekturę heksagonalną: logika domenowa i przypadki użycia nie zależą od bibliotek modeli, transportu, GUI, sprzętu ani symulatora.
- Porty opisuj małymi interfejsami, np. `typing.Protocol`. Konkretne integracje implementuj jako adaptery.
- Stosuj dependency injection: zależności przekazuj jawnie do korzystających z nich komponentów. Unikaj monkey patchingu; w testach podstawiaj zależności przez te same interfejsy.
- Narzędzia zewnętrzne opakowuj zgodnie z pełnioną funkcją. Zachowaj wymienność czujników, percepcji, modelu decyzyjnego, komunikacji i wykonania poleceń lotu.
- Współdziel kontrakty między symulacją a integracją sprzętową. Wybór adapterów i ich konfiguracja odbywają się na brzegu aplikacji.
- Zachowaj granicę między decyzją o działaniu a jego wykonaniem. Początkowo wykonanie poleceń zapewnia adapter autopilota lub symulatora.
- Rozdziel przetwarzanie poleceń operatora, percepcję, podejmowanie decyzji i sterowanie. Nie przenoś logiki domenowej do adapterów.
- Kontrakty danych muszą określać znaczenie pól, jednostki, układy współrzędnych i czas pomiaru. Rozróżniaj brak czujnika, brak obserwacji i błąd odczytu.
- Dla embeddingów określ pochodzenie, wersję modelu i wymiar. Nie zakładaj zgodności przestrzeni różnych modeli ani mniejszego kosztu transmisji bez pomiaru.
- Nie zmieniaj hierarchii instrukcji ani pierwszeństwa poleceń GUI jako ubocznego skutku implementacji.
- Zmiany kontraktów aktualizuj jednocześnie po stronie producentów, odbiorców, testów i dokumentacji.

## Python, pakowanie i zależności

- Wymagany Python: `>=3.12`. Zależności i środowiska zarządzane przez `uv`; konfiguracja w `pyproject.toml`, plik `uv.lock` w repozytorium.
- Stosuj układ `src/<nazwa_pakietu>/` i osobny katalog `tests/`. Pakiet musi dać się zbudować i zainstalować bez ręcznego modyfikowania `PYTHONPATH`.
- Grupa `basic` obejmuje inferencję i jej otoczenie. Grupa `dev` obejmuje trening, testowanie i narzędzia developerskie. Zależności treningowe nie mogą być wymagane do samej inferencji.
- Oddzielaj kod treningu od ścieżki inferencji, zachowując wspólne definicje modeli i kontrakty tam, gdzie są potrzebne.
- Nie uruchamiaj treningu, pobierania wag, połączeń sieciowych ani inicjalizacji GPU podczas importowania modułu.
- Przed wyborem narzędzia sprawdź jego utrzymanie, zgodność z Pythonem, ekosystem i licencję. Popularność repozytorium jest wskazówką, nie gwarancją jakości.
- Wymagana jest możliwość darmowego zastosowania komercyjnego. Osobno sprawdzaj licencje kodu, wag i danych. Wariant Ultralytics stanowi wskazany wyjątek wymagający opisania warunków użycia.
- Przestrzegaj ograniczeń pamięci i opóźnień urządzenia pokładowego opisanych w dokumentacji. Wyników z mocnego serwera nie przedstawiaj jako potwierdzenia działania na urządzeniu docelowym.

## Test driven development

- Testy pisz w `pytest`. Organizuj je w osobnych plikach i katalogach odpowiadających testowanym modułom. Współdzielone fixtures umieszczaj w `conftest.py` na odpowiednim poziomie, jeśli są potrzebne.
- Nowe zachowanie i poprawki błędów rozwijaj w cyklu: test opisujący wymaganie, potwierdzona porażka, minimalna implementacja, refaktoring.
- Test ma sprawdzać obserwowalne zachowanie lub kontrakt, a nie kopiować strukturę implementacji. Poprawka błędu powinna pozostawić test regresyjny.
- Testy muszą być niezależne od konkretnych wartości w roboczych i przykładowych konfiguracjach repozytorium. Jeżeli poprawna zmiana wartości w takim pliku powoduje porażkę testu, popraw test. Gdy do sprawdzenia zachowania potrzebujesz określonych danych, użyj fixture przeznaczonej do testów albo utwórz konfigurację w `tmp_path`. Testy ładowania konfiguracji sprawdzają kontrakt, walidację i interpretację danych na kontrolowanych wejściach.
- Logikę domenową testuj bez GPU, sieci i sprzętu. Stosuj małe atrapowe adaptery; unikaj rozbudowanego mockowania szczegółów bibliotek.
- Testy integracyjne adapterów oddziel od szybkich testów jednostkowych. Wymagania sprzętowe i sposób uruchomienia oznaczaj jawnie.
- Sprawdzaj brakujące i opóźnione obserwacje, błędne polecenia oraz przerwanie wykonania, gdy dotyczą zmienianego zachowania.
- Scenariusze symulacji i eksperymenty muszą mieć kontrolowane ziarna losowości. Zapisuj konfigurację, wersje modeli i metryki potrzebne do odtworzenia wyniku.
- Dla modeli oceniaj jakość, opóźnienie i zużycie pamięci. Oddziel test poprawności kodu od oceny skuteczności wytrenowanego modelu.
- Zmiany wyłącznie dokumentacyjne nie wymagają sztucznych testów kodu; sprawdź spójność treści i odnośników.

## Weryfikacja i CI

- Używaj poleceń z repozytorium przez `uv run`. Nie wymyślaj poleceń ani nie zakładaj istnienia narzędzi, których jeszcze nie skonfigurowano.
- GitHub Actions powinny sprawdzać testy, linting, formatowanie, typowanie oraz budowanie pakietu i jego podstawowy import po instalacji.
- CI musi uwzględniać minimalną wspieraną wersję Pythona. Szybkie kontrole nie powinny wymagać GPU ani pobierania dużych modeli.
- Weryfikuj, że inferencja działa z zależnościami `basic`, bez przypadkowych importów z grupy `dev`.
- Trening i kosztowne testy sprzętowe uruchamiaj oddzielnie, z jawną konfiguracją środowiska.
- Po zmianie uruchom sprawdzenia adekwatne do jej zakresu. Przed przekazaniem pracy usuń nowe błędy; jeśli sprawdzenie jest zablokowane, podaj konkretną przyczynę.
- Dokumentację i przykłady aktualizuj razem ze zmianą zachowania. Nie opisuj planowanej funkcji jako już dostępnej.
