# CLI interpretacji poleceń

Pakiet `uav_onboard_planner.nlp` przekształca tekst operatora w szkic
cywilnej misji drona. Przy każdym pytaniu o pole aplikacja daje modelowi
fragmenty bieżącej wypowiedzi i opcję braku odpowiedzi. Model wybiera
jedną opcję, a aplikacja składa JSON i wektoryzuje wartości przyjętego szkicu.

## Uruchomienie

Moduł `uav_onboard_planner.communication_cli` przyjmuje wypowiedzi operatora
w terminalu i wyświetla wynik sesji NLP.

Z katalogu głównego repozytorium:

```sh
uv sync --extra nlp
uv run --extra nlp python -m uav_onboard_planner.communication_cli
```

Wpisuj polecenia po angielsku, np. „Transport crate A to point B”, a potem
„Deliver it to point C instead”. Terminal pokazuje `USER_INSTRUCTION`
nad wejściem aż do przyjęcia pierwszej instrukcji. Kolejne wypowiedzi
wpisuje się pod `USER_PROMPT`. Wynik JSON jest wyświetlany z wcięciami.
Wejście z potoku, `--text` i odtwarzanie
scenariusza zwracają jeden obiekt JSON na wiersz. Zakończ sesję przez Ctrl+D.

Pierwsze uruchomienie pobiera wagi i pliki tokenizerów do `weights/`.
Kolejne uruchomienia korzystają z tego cache’u. `HF_HOME` pozwala wskazać
inną lokalizację. Dane w `weights/` są ignorowane przez Git.

## Profile i prompt

| Plik | Ustawienia |
| --- | --- |
| [System One](../configs/nlp/systemone/default.ini) | Identyfikator modelu z Hugging Face, rewizja, urządzenie, precyzja `bfloat16` lub `float16`, limit kontekstu i ścieżka promptu. |
| [Embeddingi](../configs/nlp/embeddings/default.ini) | Model i rewizja, urządzenie, precyzja, limit tokenów na tekst, rozmiar partii, pooling i normalizacja. |
| [Profil domyślny](../configs/nlp/prompts/default_template.yaml) | Teksty i pytania używane przy domyślnym uruchomieniu CLI. |
| [Profil transportowy](../configs/nlp/prompts/cargo_template.yaml) | Alternatywny profil misji transportowej. |

Profil misji wskazuje `prompt_file` w pliku INI System One. Ścieżka
względna jest liczona od katalogu tego pliku. Własne ustawienia można
przekazać przez `--systemone-config`, a ustawienia enkodera przez
`--embedding-config`.
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

`confidence` podaje dla każdego pola prawdopodobieństwo wybranej opcji
względem pozostałych kandydatów, w tym opcji braku odpowiedzi. Wynik Qwen
w tym adapterze nie jest skalibrowaną miarą trafności. Klucz `min_confidence`
na najwyższym poziomie profilu YAML ustala próg od 0 do 1. Domyślna wartość
to `0.6`. Jeśli dowolne pole ma wynik poniżej progu, CLI pokazuje je
w `low_confidence`, zachowuje
dotychczasową instrukcję i prosi o precyzyjniejszą wypowiedź nad etykietą wejścia.

W CLI `embeddings` podaje identyfikator modelu, rewizję i wymiar.
Kod korzystający z sesji ma też dostęp do wektorów według nazw pól.
`target` otrzymuje jeden wektor, a wektory listy `constraints` zachowują
kolejność elementów.

Aby dodać profil, zdefiniuj cztery typy instrukcji jak w profilu transportowym.
W `fields` sekcji `SYSTEM` i `GENERAL_INSTRUCTION` wpisz
gotowe wartości. W sekcjach operatora pod `fields` wpisz pytanie do
System One dla każdego pola. Mapa `required` podaje osobną wartość
`true` lub `false` dla każdego z nich. Lista lub mapa w wartościach
`GENERAL_INSTRUCTION` określa też typ pola o tej nazwie w instrukcjach
operatora. Pozostałe pola są tekstowe. Można nadal wczytać
starsze profile z `default_text` albo pojedynczym kluczem `system`.

## Testy

Testy korzystają z własnego profilu w `tests/fixtures/`, własnych
wypowiedzi w `tests/scenarios/` i atrap modeli z ustalonymi odpowiedziami.
