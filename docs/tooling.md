# Narzędzia developerskie i CI

Python >=3.12, środowisko i zależności zarządzane przez `uv`.

```sh
uv sync --locked
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest
uv build
```

Ruff odpowiada za lint i formatowanie, mypy za typowanie. Narzędzia należą
do grupy `dev`; nie są wymagane w środowisku `basic`.

Workflow `CI` uruchamia te kontrole na Ubuntu i Pythonie 3.12 przy pushu,
pull requeście i ręcznym uruchomieniu. Sprawdza też import zainstalowanego
wheel w osobnym środowisku bez grupy `dev` oraz import po synchronizacji
samej grupy `basic`. Testy nie wymagają GPU ani wag modeli.

Workflow `PR title` sprawdza tytuł zgodnie z [CONTRIBUTING.md](../CONTRIBUTING.md).
Nie wykonuje kodu pull requesta. Uprawnienia workflow ograniczono do minimum.
Włączenie tych kontroli jako obowiązkowych w ochronie brancha jest osobnym
ustawieniem repozytorium; same pliki workflow go nie zmieniają.
