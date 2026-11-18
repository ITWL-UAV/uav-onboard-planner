# CLI interpretacji poleceń

Pakiet `uav_onboard_planner.nlp` przekształca tekst operatora w szkic
cywilnej misji drona. System One odpowiada tekstowo na pytania o pola
misji. Aplikacja waliduje odpowiedzi, składa z nich JSON i przekazuje
wartości tekstowe do osobnego modelu embeddingów.

## Uruchomienie

Moduł `uav_onboard_planner.communication_cli` przyjmuje wypowiedzi operatora
w terminalu i wyświetla wynik sesji NLP.

Z katalogu głównego repozytorium:

```sh
uv sync --extra nlp
uv run --extra nlp python -m uav_onboard_planner.communication_cli
```

Wpisuj polecenia po angielsku, np. „Transport crate A to point B”, a potem
„Deliver it to point C instead”. Terminal prosi o tekst przez `User prompt:`
i pokazuje JSON z wcięciami. Wejście z potoku, `--text` i odtwarzanie
scenariusza zwracają jeden obiekt JSON na wiersz. Zakończ sesję przez Ctrl+D.

Pierwsze uruchomienie pobiera wagi i pliki tokenizerów do `weights/`.
Kolejne uruchomienia korzystają z tego cache’u. `HF_HOME` pozwala wskazać
inną lokalizację. Dane w `weights/` są ignorowane przez Git.

## Profile i prompt

| Plik | Ustawienia |
| --- | --- |
| [System One](../configs/nlp/systemone/default.ini) | Identyfikator modelu z Hugging Face, rewizja, urządzenie, precyzja `bfloat16` lub `float16`, łączny limit tokenów wejścia i generacji, limit generacji, ścieżka promptu. |
| [Embeddingi](../configs/nlp/embeddings/default.ini) | Model i rewizja, urządzenie, precyzja, limit tokenów na tekst, rozmiar partii, pooling i normalizacja. |
| [Profil transportowy](../configs/nlp/prompts/cargo_template.yaml) | Teksty domyślne i pytania dla misji transportowej. |

Profil można podmienić przez `--systemone-config` albo `--embedding-config`.
Ustawienie `device = auto` wybiera CUDA, MPS lub CPU w tej kolejności.
Przekroczenie `context_size` powoduje jawny błąd. W razie potrzeby przypnij
konkretny commit Hugging Face w `revision`.

System One używa domyślnie [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B),
a wektoryzacja [Snowflake/snowflake-arctic-embed-m-v2.0](https://huggingface.co/Snowflake/snowflake-arctic-embed-m-v2.0).
Domyślny profil embeddingów wykorzystuje wektor CLS z normalizacją L2.
Modele zastępcze muszą korzystać z formatu wag Safetensors. Model językowy
musi obsługiwać tekst i szablon rozmowy, a enkoder zwracać stan ukryty
tokenów. Sprawdź wymagane pooling i normalizację na karcie wybranego modelu.

## Wynik

Sesja wczytuje `SYSTEM` i `GENERAL_INSTRUCTION` bez interpretacji i wektoryzacji.
`SYSTEM` jest dosłownym kontekstem przeznaczenia drona. Domyślne zadanie
określa typ czynności. Pierwsza przyjęta wypowiedź staje
się `USER_INSTRUCTION` i zastępuje całe domyślne zadanie.
Kolejne wypowiedzi stają się zmianami `USER_PROMPT`. Sesja przekazuje
modelowi pierwotne polecenie, zaakceptowane zmiany i oczekujące doprecyzowanie.
Niekompletny szkic zachowuje dotychczasowy stan misji. Następna wypowiedź
może uzupełnić brakujące dane.

Szkic zawiera `schema_version`, `instruction` oraz jawne pola w `draft`.
`USER_INSTRUCTION` wymaga `target`, a `activity` i listę `constraints`
traktuje jako opcjonalne. `USER_PROMPT` ma `change`, zaktualizowany `target`
i opcjonalne zmiany ograniczeń. `target` to krótka fraza podawana przez
operatora, np. `point B`. Brakujące wartości w `draft` mają postać
`null`. Pole `missing_required` wymienia braki blokujące przyjęcie szkicu
i jego wektoryzację.

`embeddings` podaje identyfikator modelu, rewizję, wymiar i wektory
według nazw pól. `target` otrzymuje jeden wektor, a wektory listy
`constraints` zachowują kolejność elementów.

Aby dodać profil, zdefiniuj cztery typy instrukcji jak w profilu transportowym.
W `fields` sekcji `SYSTEM` i `GENERAL_INSTRUCTION` wpisz
gotowe wartości. W sekcjach operatora pod `fields` wpisz pytanie do
System One dla każdego pola. Mapa `required` podaje osobną wartość
`true` lub `false` dla każdego z nich. Lista lub mapa w wartościach
`GENERAL_INSTRUCTION` określa też typ pola o tej nazwie w instrukcjach
operatora. Pozostałe pola są tekstowe. Można nadal wczytać
starsze profile z `default_text` albo pojedynczym kluczem `system`.

## Odtwarzanie scenariusza

```sh
uv run --extra nlp python -m uav_onboard_planner.communication_cli \
  --scenario scenarios/cargo_edits.yaml --conversation change-destination --seed 7
```

Plik YAML przypisuje identyfikatorom rozmów listy wypowiedzi. Każda tura
ma `time` w sekundach od początku epizodu i `text` z jedną wypowiedzią
lub listą równoważnych wariantów. Czasy są uporządkowane niemalejąco.
Wypowiedzi o tym samym czasie są dostarczane w kolejności z pliku.
CLI odtwarza kolejne chwile bez czekania. Kod prowadzący epizod może
przekazywać bieżący czas symulacji do `Replay.advance(elapsed)`.

Odpowiedzi JSON trafiają na standardowe wyjście. Rekord na standardowym
wyjściu błędów zawiera identyfikator rozmowy, ziarno i dostarczone
wypowiedzi wraz z czasami. Domyślne ziarno to 0.

Pliki w [scenarios/](../scenarios/) zawierają czasy i wypowiedzi operatora.
Oczekiwane typy instrukcji i wartości pól sprawdzają testy w katalogach
`tests/nlp/` i `tests/communication_cli/`.

Testy korzystają z własnego profilu w `tests/fixtures/`, własnych
wypowiedzi w `tests/scenarios/` i atrap modeli z ustalonymi odpowiedziami.
