# CLI interpretacji poleceń

Pakiet `uav_onboard_planner.nlp` przekształca tekst operatora w podgląd
szkicu cywilnej inspekcji budynków. Model System One zwraca listę miejsc
albo pytanie o doprecyzowanie. Dla zaakceptowanego szkicu osobny model
oblicza jeden embedding na każde miejsce.

## Uruchomienie

Z katalogu głównego repozytorium:

```sh
uv sync --extra nlp
uv run --extra nlp python -m uav_onboard_planner.nlp
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
| [Prompt](../configs/nlp/prompts/inspection.yaml) | Angielska dyrektywa określająca przeznaczenie drona oraz reguły interpretacji i wyjścia JSON. Ścieżka w profilu System One jest względna wobec tego profilu. |

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

Szkic ma `schema_version`, typ instrukcji i pole `draft.sites` z jawną
listą miejsc. `embeddings.fields.sites` zawiera wektory w tej samej kolejności.
Obiekt `embeddings` podaje identyfikator modelu, rewizję i liczbę wymiarów.
Pierwsza przyjęta instrukcja ma typ `USER_INSTRUCTION`, a zmiany typu
`USER_PROMPT` aktualizują szkic. Pytanie o doprecyzowanie nie modyfikuje
zaakceptowanej listy i nie wywołuje enkodera.
