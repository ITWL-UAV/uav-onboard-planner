# CLI interpretacji poleceń

Pakiet `uav_onboard_planner.nlp` przekształca tekst operatora w podgląd
szkicu cywilnej inspekcji budynków. Model System One zwraca listę miejsc
albo pytanie o doprecyzowanie. Dla zaakceptowanego szkicu osobny model
oblicza jeden embedding na każde miejsce.

## Uruchomienie

Moduł `uav_onboard_planner.communication_cli` przyjmuje wypowiedzi operatora
w terminalu i wyświetla wynik sesji NLP.

Z katalogu głównego repozytorium:

```sh
uv sync --extra nlp
uv run --extra nlp python -m uav_onboard_planner.communication_cli
```

Wpisz np. „Zaplanuj inspekcję dachu A i dachu B”, a potem „Jednak pomiń
drugi dach”. Każdy wiersz wyjścia to osobny obiekt JSON. Zakończ wejście
przez Ctrl+D albo użyj `--text "Zaplanuj inspekcję dachu A"` do wykonania
pojedynczej tury. Pierwsze użycie pobiera skonfigurowane wagi z Hugging
Face. Oba modele działają na urządzeniu wskazanym w ich profilach.

## Profile i prompt

| Plik | Ustawienia |
| --- | --- |
| [System One](../configs/nlp/systemone/default.ini) | Identyfikator modelu z Hugging Face, rewizja, urządzenie, precyzja `bfloat16` lub `float16`, łączny limit tokenów wejścia i generacji, limit generacji, ścieżka promptu. |
| [Embeddingi](../configs/nlp/embeddings/default.ini) | Model i rewizja, urządzenie, precyzja, limit tokenów na tekst, rozmiar partii, pooling i normalizacja. |
| [Profil przeznaczenia](../configs/nlp/prompts/inspection_template.yaml) | Teksty domyślne i schematy pól dla czterech typów instrukcji. Ścieżka w profilu System One jest względna wobec tego profilu. |

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

Przy starcie sesja przekazuje `SYSTEM` dosłownie jako kontekst przeznaczenia
drona i interpretuje `GENERAL_INSTRUCTION` jako ogólne zadanie domyślne.
W profilu inspekcji obejmuje ono rozpoznanie wyznaczonego obszaru
i udokumentowanie widocznego stanu zewnętrznego budynków.
Pierwsza przyjęta wypowiedź staje się `USER_INSTRUCTION` i zastępuje domyślne
zadanie. Kolejne wypowiedzi stają się zmianami `USER_PROMPT`. Sesja przekazuje
modelowi pierwotne polecenie, zaakceptowane zmiany i oczekujące doprecyzowanie.
Pytanie o doprecyzowanie pozostawia zaakceptowany stan i nie wywołuje enkodera.

Szkic zawiera `schema_version`, `instruction` oraz jawne pola w `draft`.
Pole `embeddings` pojawia się, jeśli profil wyznacza obecne pola do wektoryzacji.
Zawiera identyfikator modelu, rewizję, wymiar i wektory według nazw pól.
Pole tekstowe dostaje jeden wektor. Dla listy tekstów, np. `draft.sites`,
`embeddings.fields.sites` zachowuje kolejność elementów. W profilu inspekcji
nakładane ograniczenia zachowują zapisane liczby i jednostki w jawnej treści.

Aby dodać profil, zdefiniuj cztery typy instrukcji jak w przykładzie
inspekcji. Sekcje operatora mają `default_text: null`, a pozostałe zawierają
tekst domyślny. Pod `json_extraction` zdefiniuj pola dla trzech pozostałych
typów instrukcji. Tekst `SYSTEM` jest używany w całości.
Każde pole określa pytanie przekazywane do System One (`question`), typ
`text` lub `text_list`, wymagalność (`required`) i wektoryzację (`embed`).
Opcjonalna sekcja `constraints` definiuje pole `draft.constraints` dla
wskazanych typów instrukcji, używając tych samych czterech ustawień.
Można nadal wczytać profile z polami `fields` i opisami `meaning` oraz
wcześniejsze profile z pojedynczym kluczem `system`.

## Odtwarzanie scenariusza

```sh
uv run --extra nlp python -m uav_onboard_planner.communication_cli \
  --scenario scenarios/inspection_edits.yaml --conversation change-order --seed 7
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

Opcja `--check-scenario` porównuje odpowiedzi z oczekiwaniami z YAML.
`expected: true` oznacza oczekiwane pytanie, a mapa pól oznacza oczekiwane
wartości w szkicu. Numery niezgodnych tur trafiają do `mismatches`;
niezgodność daje kod wyjścia 1. Interpretator otrzymuje samą wypowiedź
i kontekst sesji. Przykłady rozmów znajdują się w [scenarios/](../scenarios/).
