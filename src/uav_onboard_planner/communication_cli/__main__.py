import argparse
import json
import sys
from configparser import Error as ConfigError
from pathlib import Path
from typing import TextIO

from ..nlp.config import EmbeddingConfig, PromptProfile, SystemOneConfig, load_prompt
from ..nlp.huggingface import HuggingFaceEncoder, HuggingFaceSystemOne
from ..nlp.scenario import Conversation, Replay, load_conversation
from ..nlp.session import Session


def run_terminal(
    session: Session, source: TextIO, output: TextIO, errors: TextIO
) -> None:
    while True:
        if source.isatty():
            print("Operator> ", end="", file=errors, flush=True)
        line = source.readline()
        if not line:
            return
        if line.strip():
            try:
                print(session.submit(line.strip()).to_json(), file=output, flush=True)
            except ValueError as error:
                print(f"Błąd: {error}", file=errors)


def run_replay(
    session: Session,
    conversation: Conversation,
    output: TextIO,
    metadata: TextIO,
    *,
    check: bool = False,
) -> int:
    delivered: list[dict[str, str | float]] = []
    mismatches: list[int] = []
    try:
        replay = Replay(session, conversation)
        for scheduled in conversation.turns:
            for turn, reply in replay.advance(scheduled.time):
                delivered.append({"time": turn.time, "text": turn.text})
                print(reply.to_json(), file=output, flush=True)
                if check and not turn.matches(reply):
                    mismatches.append(len(delivered))
    finally:
        record = {
            "conversation": conversation.identifier,
            "seed": conversation.seed,
            "turns": delivered,
        }
        if check:
            record["mismatches"] = mismatches
        print(json.dumps(record, ensure_ascii=False), file=metadata, flush=True)
    return int(bool(mismatches))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interpret operator instructions as JSON."
    )
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
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="Process one message instead of reading stdin.")
    source.add_argument("--scenario", type=Path, help="Replay a YAML conversation.")
    parser.add_argument(
        "--conversation", help="Conversation identifier in the YAML file."
    )
    parser.add_argument(
        "--seed", type=int, help="Seed for selecting utterance variants."
    )
    parser.add_argument(
        "--check-scenario", action="store_true", help="Check expected replies."
    )
    args = parser.parse_args()
    if args.scenario is not None and args.conversation is None:
        parser.error("--scenario requires --conversation")
    if args.scenario is None and (
        args.conversation is not None or args.seed is not None or args.check_scenario
    ):
        parser.error("--conversation, --seed and --check-scenario require --scenario")

    try:
        conversation = (
            load_conversation(args.scenario, args.conversation, args.seed or 0)
            if args.scenario is not None
            else None
        )
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
        if conversation is not None:
            return run_replay(
                session, conversation, sys.stdout, sys.stderr, check=args.check_scenario
            )
        run_terminal(session, sys.stdin, sys.stdout, sys.stderr)
        return 0
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
