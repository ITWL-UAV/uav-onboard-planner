# Symulacja lotu i misji

Pierwsza wersja obsługuje wiele quadkopterów i stałopłatów we wspólnym czasie
symulacji. Każdy pojazd ma własną trasę i instancję dynamiki. Identycznie można
modelować drona wykonującego misję i pozostały ruch w otoczeniu.

## Uruchomienie

```sh
uv sync
uv run python -m uav_onboard_planner.simulation \
  --config configs/simulation/scenarios/default.yaml \
  --output /tmp/uav-flight-001
```

Katalog wyjściowy musi być nowy. Wyniki obejmują:

- `trajectory.csv`: czas, identyfikator pojazdu, pozycję, prędkość, status misji
  oraz indeks kolejnego punktu (liczony od zera).
- `trajectory.png`: trajektorie w 3D.
- `altitude.csv` (dla scenariuszy z wysokościomierzem): pomiary wysokości,
  czas ich wykonania, czas dostępności i czas odbioru w symulacji.
- `run.json`: pełną konfigurację, wersje bibliotek i Pythona, końcowe statusy misji.

`show_animation: true` w YAML otwiera po obliczeniach animację przebiegu
w oknie Matplotlib. Nie jest to podgląd na żywo. Bez środowiska graficznego
pozostaw `false`; wykres nadal zostanie zapisany.

Po wykonaniu epizodu `run.json` podaje `end_reason` i czas ostatniego pełnego
kroku. Przy limicie czasu status przebiegu to `finished`, a przy błędzie kroku
`failed`. Nieukończona misja pozostaje `active`. Częściowe pliki CSV są zachowywane.

## Konfiguracja

Scenariusze lotu są w `configs/simulation/scenarios/`. Domyślny przykład to
`configs/simulation/scenarios/default.yaml`. Profile wielokrotnego użytku są
w `configs/simulation/`. Przekaż ścieżkę do scenariusza przez `--config`.
Archiwum źródłowe zawiera przykładowe scenariusze i profile.

| Pole | Znaczenie |
| --- | --- |
| `time_step` | Krok dynamiki w sekundach, dodatni i nie większy niż 0,02 s. |
| `duration` | Czas trwania symulacji w sekundach. |
| `sample_interval` | Odstęp zapisu w sekundach, co najmniej równy krokowi dynamiki. |
| `seed` | Ziarno JSBSim, liczba całkowita z zakresu `[0, 2**32)`. |
| `show_animation` | Czy odtworzyć animację po obliczeniach. |
| `drones` | Niepusta lista pojazdów z unikalnymi nazwami. |
| `route_changes` | Opcjonalna lista zmian trasy w trakcie epizodu. |
| `mission_cancellations` | Opcjonalna lista anulowań aktywnych misji w trakcie epizodu. |

Każdy pojazd określa `name`, `backend`, `model`, `position`, `speed`, `heading`,
`arrival_radius` i niepustą listę `waypoints`. Te pola są wymagane;
nieznane pola, backendy i modele są odrzucane, żeby literówki nie uruchamiały
niezamierzonego wariantu. YAML jest odczytywany przez `safe_load`.

Każdy typ czujnika ma własny moduł w `simulation/sensors/` i osobny plik
ustawień w `configs/simulation/sensors/`. W scenariuszu zmiany trasy wpis
`altimeter: ../sensors/altimeter.yaml` włącza
wysokościomierz dla pojazdu.
Ścieżka względna jest liczona od katalogu pliku scenariusza.
[Konfiguracja wysokościomierza](../configs/simulation/sensors/altimeter.yaml)
zawiera `noise_std_m` (odchylenie standardowe szumu Gaussa w metrach)
i `delay_s` (opóźnienie w sekundach symulacji). Obie wartości są nieujemne.
W starszych scenariuszach pole `altimeter` może też zawierać obie wartości
bezpośrednio. Rejestr `run.json` zapisuje w obu przypadkach wczytane ustawienia.

Pozycje i punkty trasy są trójkami `[wschód, północ, góra]` w metrach, w lokalnym
układzie ENU. Płaski grunt ma wysokość 0. Pojazdy zaczynają powyżej gruntu;
start i lądowanie nie są obsługiwane. `heading` to kurs w stopniach zgodnie
z ruchem wskazówek zegara od północy. `arrival_radius` to promień kuli
zaliczenia punktu w metrach, sprawdzany po każdym kroku dynamiki.
Próbkowanie pliku odbywa się na pierwszym kroku osiągającym zadany czas próbki;
próbka początkowa i końcowa zawsze są zapisywane.

## Zaplanowana zmiana trasy i anulowanie misji

[Scenariusz z jednym quadkopterem](../configs/simulation/scenarios/route_change.yaml)
rozpoczyna lot po dwóch punktach. Po 2 s zastępuje pozostałą trasę jednym
nowym punktem. Uruchom go tą samą komendą co przykład domyślny, podając
`--config configs/simulation/scenarios/route_change.yaml` i nowy katalog wyników.

Każda zmiana określa `time` w sekundach od początku, `drone`, `waypoints`
i `arrival_radius`. Czas musi wypadać wewnątrz epizodu. Dwie zmiany dla
jednego pojazdu w tej samej chwili są odrzucane. Epizod skraca krok dynamiki,
jeśli trzeba dojść do chwili zmiany, i stosuje nową trasę przed następnym
krokiem. Indeks punktu wraca wtedy do zera.

Każde anulowanie w `mission_cancellations` określa `time` w sekundach od
początku epizodu i `drone`. Czas musi wypadać wewnątrz epizodu. Zdarzenia
tego samego pojazdu w tej samej chwili są odrzucane, także gdy jedno zmienia
trasę, a drugie anuluje misję. W chwili anulowania aktywna misja otrzymuje
status `cancelled`. Pojazd przechodzi w tryb podtrzymania lotu swojego
adaptera, a pozostałe loty trwają według ich misji. Ukończona wcześniej
misja zachowuje status `completed`.

[Scenariusz anulowania](../configs/simulation/scenarios/mission_cancellation.yaml)
zmienia trasę quadkoptera po 1 s, anuluje jego misję po 2,505 s i prowadzi
lot stałopłata do końca epizodu. Uruchom go z
`--config configs/simulation/scenarios/mission_cancellation.yaml`.

Do uruchomienia w pamięci służy `create_episode(load_config(path))` z modułów
`runner` i `config`. `snapshot()` zwraca bieżące próbki lotu, `step()`
przesuwa epizod o jeden krok, a `finished` sygnalizuje koniec epizodu.
W trakcie epizodu `outcome` ma wartość `None`. Po zakończeniu podaje przyczynę
(`time_limit`, `interrupted` po wywołaniu `stop()` między krokami lub `error`)
i czas ostatniego pełnego kroku. `reset()` tworzy od nowa pojazdy i harmonogram.
Próbki zawierają stan symulatora i status misji. Po błędzie z adaptera odczyt próbki
i dalsze kroki wymagają resetu.

### Polecenia w trakcie epizodu

Między wywołaniami `step()` można wywołać
`episode.replace_mission(drone, mission)` albo `episode.cancel_mission(drone)`.
`drone` to nazwa pojazdu z konfiguracji, a `mission` to obiekt `Mission`
z punktami nad gruntem i promieniem zaliczenia. Wynik polecenia widać
w `snapshot()` od razu. Zegar symulacji przesuwa się dopiero przy `step()`.

Harmonogram z YAML nadal obowiązuje, więc późniejsze zaplanowane zdarzenie
może ponownie zmienić misję. Reset odtwarza stan początkowy i harmonogram.
Do odtworzenia ręcznych poleceń należy ponownie podać je w tych samych chwilach.
Po zakończeniu lub awarii epizod wymaga resetu przed przyjęciem polecenia.

## Odczyty wysokościomierza

`episode.altitude_observations()` zwraca ostatni dostępny odczyt dla
każdego wyposażonego pojazdu. Brak klucza oznacza brak wysokościomierza,
a `None` oznacza oczekiwanie na pierwszy odczyt. Odczyt zawiera wysokość
w metrach nad płaskim gruntem symulacji, czas pomiaru i najwcześniejszy
czas jego udostępnienia. Próbka powstaje w chwili zero i po każdym kroku
fizyki. Jest widoczna od pierwszego kroku, który osiągnie czas dostępności.
Reset z tym samym ziarnem odtwarza sekwencję szumu.

`episode.altitude_updates()` zwraca wszystkie pomiary udostępnione na
bieżącym kroku. CLI zapisuje tę samą partię do `altitude.csv`.
`available_at_s` oznacza czas pomiaru powiększony o opóźnienie z profilu,
a `received_at_s` jest czasem kroku, w którym pomiar stał się widoczny.
Pomiary niedostarczone przed końcem epizodu nie trafiają do pliku.
Częstotliwość zapisu trajektorii nie wpływa na zapis pomiarów.

Opcjonalna lista `outages` w profilu wysokościomierza zawiera
uporządkowane, nienakładające się przedziały `[start_s, end_s)`. Czasy są
liczone od początku epizodu. Przerwa usuwa ostatni odczyt i próbki oczekujące
na dostarczenie. Po wznowieniu odczyt znów przechodzi przez opóźnienie profilu.
Przedziały są oceniane na krokach fizyki. Przerwa mieszcząca się w całości
między krokami usuwa stare próbki, ale może nie dać osobnego kroku ze
statusem niedostępności.

`episode.altimeter_statuses()` zwraca dla każdego pojazdu
`not_equipped`, `waiting`, `unavailable` albo `available`. W CSV przerwę
widać jako lukę w dostarczonych pomiarach. Przykład z oknem od 1,25 s do 2 s
jest w [osobnym profilu YAML](../configs/simulation/sensors/altimeter_with_outage.yaml)
używanym przez scenariusz anulowania misji.

## Backend quadkoptera

`backend: rotorpy` obsługuje `model: hummingbird` oraz `model: crazyflie`.
[RotorPy](https://github.com/spencerfolk/rotorpy) dostarcza model dynamiki
`Multirotor`, parametry pojazdów oraz gotowy kontroler `SE3Control`.
Adapter przesuwa referencję pozycji w kierunku punktu trasy z prędkością
`speed` w m/s. Faktyczna prędkość wynika z dynamiki i pracy kontrolera;
`speed` nie jest twardym ograniczeniem prędkości fizycznej.

Quadkopter zaczyna w zawisie. Wiatr i szum silników są wyłączone; wyniki tego
adaptera są deterministyczne i nie wymagają losowania scenariusza.
Po ukończeniu lub anulowaniu misji kontroler próbuje utrzymać pozycję zmierzoną
w momencie przejścia. Hamowanie wynika z dynamiki, nie jest natychmiastowe.

## Backend stałopłata

`backend: jsbsim` obsługuje obecnie `model: c172x`.
[JSBSim](https://github.com/JSBSim-Team/jsbsim) dostarcza model samolotu,
trymowanie i dołączony autopilot utrzymywania kursu oraz wysokości.
Adapter wyznacza kurs do następnego punktu; nie implementuje własnych
macierzy sterowania ani regulatorów lotu.

`speed` oznacza początkową prędkość rzeczywistą w m/s, przy której samolot
jest trymowany. Przepustnica pozostaje w ustawieniu trymowania — nie ma
regulacji zadanej prędkości podczas zakrętów. Przykład używa 50 m/s.
Po ukończeniu lub anulowaniu misji stałopłat utrzymuje aktualny kurs i wysokość,
kontynuując lot. Nie może zawisnąć. Punkty muszą uwzględniać promień zakrętu;
zbyt ciasna trasa lub mały promień zaliczenia mogą nie zostać wykonane.

Pozycję geograficzną JSBSim przeliczamy na lokalną płaską mapę przy równiku
z początkiem na szerokości i długości 0°. To przybliżenie dla lokalnych
scenariuszy rzędu kilku kilometrów, nie model nawigacji globalnej.
Model C172 jest modelem referencyjnym samolotu, nie skalibrowanym modelem
konkretnego bezzałogowca. Inny model wymaga sprawdzenia jego autopilota
i parametrów, a następnie rozszerzenia adaptera i walidacji konfiguracji.

## Granice modułów

`contracts.py` definiuje `FlightState`, `Mission` i port `Autopilot`, korzystając
wyłącznie z biblioteki standardowej. Stan opisuje rzeczywistą pozycję i prędkość
w czasie symulacji, nie odczyt zaszumionego lub opóźnionego czujnika.

`mission.py` realizuje kolejność punktów, ukończenie, zmianę i anulowanie misji.
`Flight.replace_mission()` zastępuje aktualną trasę od razu;
`Flight.cancel()` przerywa trasę i zleca podtrzymanie lotu właściwe dla pojazdu.
Nie rozstrzygamy tu pierwszeństwa poleceń GUI i LLM.

`adapters/` zawiera integracje bibliotek. `runner.py` jest miejscem wyboru
konkretnego adaptera i przekazania go do `Flight`. Podmiana biblioteki wymaga
implementacji portu `Autopilot`, rejestracji w tym miejscu oraz aktualizacji
walidacji YAML; wykonanie misji pozostaje niezależne od biblioteki.

Nie ma fizycznych kolizji między dronami, przeszkód, unikania kolizji,
oddziaływania wirników ani modelu decyzyjnego. Przecięcie trajektorii
nie zatrzymuje lotu. Osiągnięcie poziomu gruntu lub niefinitywny stan kończy
obliczenia błędem. Awaria jednego adaptera kończy cały przebieg; krok wspólny
nie jest transakcją i wcześniej przeliczone pojazdy nie są cofane.

## Zależności i sprawdzenia

Zależności symulacyjne należą do grupy `dev`; grupa `basic` pozostaje pusta.
Import głównego pakietu i logiki misji nie inicjalizuje symulatora ani GPU.

- RotorPy: [MIT](https://github.com/spencerfolk/rotorpy/blob/main/LICENSE.md).
- JSBSim wraz z modelami dostarczonymi w dystrybucji: [LGPL-2.0-or-later](https://github.com/JSBSim-Team/jsbsim/blob/master/COPYING).
  Przy dystrybucji należy zachować warunki tej licencji; licencja MIT własnego
  pakietu nie zmienia licencji JSBSim.
- PyYAML: [MIT](https://github.com/yaml/pyyaml/blob/main/LICENSE).

Korzystamy z parametrów i modeli z zainstalowanych paczek, bez zewnętrznych wag
i zbiorów treningowych. Wersje są zapisane w `uv.lock`, a wersje silników
użytych w konkretnym przebiegu — w `run.json`.

```sh
uv run pytest -m 'not integration'
uv run pytest -m integration
uv build
```

Testy integracyjne pracują na CPU, bez sieci i sprzętu. Sprawdzają dotarcie do
punktów, podtrzymanie lotu, powtarzalność i zapis scenariusza. Nie stanowią
kalibracji dynamiki ani potwierdzenia bezpieczeństwa rzeczywistego lotu.
