import argparse
import sys
from configparser import Error as ConfigError
from pathlib import Path

from ..nlp.config import EmbeddingConfig, PromptProfile, SystemOneConfig, load_prompt
from ..nlp.huggingface import HuggingFaceEncoder, HuggingFaceSystemOne
from ..nlp.session import Session


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an inspection draft as JSON.")
    parser.add_argument(
        "--systemone-config",
        type=Path,
        default=Path("configs/nlp/systemone/default.ini"),
    )
    parser.add_argument(
        "--embedding-config",
        type=Path,
        default=Path("configs/nlp/embeddings/default.ini"),
    )
    parser.add_argument("--text", help="Process one message instead of reading stdin.")
    args = parser.parse_args()

    try:
        systemone = SystemOneConfig.load(args.systemone_config)
        embeddings = EmbeddingConfig.load(args.embedding_config)
        prompt = load_prompt(systemone.prompt_file)
        session = Session(
            HuggingFaceSystemOne(systemone, prompt),
            HuggingFaceEncoder(embeddings),
            prompt if isinstance(prompt, PromptProfile) else None,
        )
        if args.text is not None:
            print(session.submit(args.text).to_json())
            return 0

        while True:
            if sys.stdin.isatty():
                print("Operator> ", end="", file=sys.stderr, flush=True)
            line = sys.stdin.readline()
            if not line:
                return 0
            if line.strip():
                try:
                    print(session.submit(line.strip()).to_json(), flush=True)
                except ValueError as error:
                    print(f"Błąd: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        return 130
    except ModuleNotFoundError as error:
        print(
            f"{error}. Zainstaluj zależności przez uv sync --extra nlp.",
            file=sys.stderr,
        )
    except (ConfigError, OSError, RuntimeError, ValueError) as error:
        print(f"Błąd: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
