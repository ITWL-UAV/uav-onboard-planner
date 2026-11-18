# Symulacja lotu i misji

Pierwsza wersja obsługuje wiele quadkopterów i stałopłatów we wspólnym czasie
symulacji. Każdy pojazd ma własną trasę i instancję dynamiki. Identycznie można
modelować drona wykonującego misję i pozostały ruch w otoczeniu.

## Uruchomienie

```sh
uv sync
uv run python -m uav_onboard_planner.simulation \
  --config configs/simulation/default.yaml \
  --output /tmp/uav-flight-001
```

Katalog wyjściowy musi być nowy. Wyniki obejmują:

- `trajectory.csv`: czas, identyfikator pojazdu, pozycję, prędkość, status misji
  oraz indeks kolejnego punktu (liczony od zera).
- `trajectory.png`: trajektorie w 3D.
- `run.json`: pełną konfigurację, wersje bibliotek i Pythona, końcowe statusy misji.

`show_animation: true` w YAML otwiera po obliczeniach animację przebiegu
w oknie Matplotlib. Nie jest to podgląd na żywo. Bez środowiska graficznego
pozostaw `false`; wykres nadal zostanie zapisany.

Status przebiegu `finished` oznacza koniec zadanego czasu, niekoniecznie ukończenie
wszystkich misji. Nieukończona misja pozostaje `active`. Jeśli obliczenia przerwano
błędem, zachowane częściowe wyniki mają status przebiegu `running`.

## Konfiguracja

Konfiguracje dzielimy według modułu: `configs/<moduł>/*.yaml`. Obecnie istnieje
moduł `simulation` i kompletny przykład `configs/simulation/default.yaml`.
Plik jest zewnętrznym wejściem aplikacji; przy instalacji z wheel należy przekazać
własny plik przez `--config`. Archiwum źródłowe zawiera przykładową konfigurację.

| Pole | Znaczenie |
| --- | --- |
| `time_step` | Krok dynamiki w sekundach, dodatni i nie większy niż 0,02 s. |
| `duration` | Czas trwania symulacji w sekundach. |
| `sample_interval` | Odstęp zapisu w sekundach, co najmniej równy krokowi dynamiki. |
| `seed` | Ziarno JSBSim, liczba całkowita z zakresu `[0, 2**32)`. |
| `show_animation` | Czy odtworzyć animację po obliczeniach. |
| `drones` | Niepusta lista pojazdów z unikalnymi nazwami. |

Każdy pojazd określa `name`, `backend`, `model`, `position`, `speed`, `heading`,
`arrival_radius` i niepustą listę `waypoints`. Wszystkie pola są wymagane;
nieznane pola, backendy i modele są odrzucane, żeby literówki nie uruchamiały
niezamierzonego wariantu. YAML jest odczytywany przez `safe_load`.

Pozycje i punkty trasy są trójkami `[wschód, północ, góra]` w metrach, w lokalnym
układzie ENU. Płaski grunt ma wysokość 0. Pojazdy zaczynają powyżej gruntu;
start i lądowanie nie są obsługiwane. `heading` to kurs w stopniach zgodnie
z ruchem wskazówek zegara od północy. `arrival_radius` to promień kuli
zaliczenia punktu w metrach, sprawdzany po każdym kroku dynamiki.
Próbkowanie pliku odbywa się na pierwszym kroku osiągającym zadany czas próbki;
próbka początkowa i końcowa zawsze są zapisywane.

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
oddziaływania wirników, czujników ani modelu decyzyjnego. Przecięcie trajektorii
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
