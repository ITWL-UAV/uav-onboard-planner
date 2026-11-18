from collections.abc import Iterator
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from random import Random
from sys import float_info

from .session import Reply, Session


@dataclass(frozen=True)
class Turn:
    time: float
    text: str


@dataclass(frozen=True)
class Conversation:
    identifier: str
    seed: int
    turns: tuple[Turn, ...]


def load_conversation(path: Path, identifier: str, seed: int) -> Conversation:
    import yaml

    try:
        data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: invalid scenario YAML") from error
    if (
        not isinstance(data, dict)
        or not data
        or any(not isinstance(name, str) or not name.strip() for name in data)
    ):
        raise ValueError(f"{path}: expected a mapping of conversation identifiers")
    if identifier not in data:
        raise ValueError(f"{path}: unknown conversation {identifier!r}")

    entries = data[identifier]
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: {identifier} must contain at least one turn")

    random = Random(seed)
    turns: list[Turn] = []
    previous = 0.0
    for index, entry in enumerate(entries, 1):
        label = f"{path}: {identifier}, turn {index}"
        if not isinstance(entry, dict) or entry.keys() != {"time", "text"}:
            raise ValueError(f"{label}: expected time and text")
        time = entry["time"]
        if type(time) not in (float, int) or not previous <= time <= float_info.max:
            raise ValueError(f"{label}: time must be finite, nonnegative and ordered")
        variants = entry["text"]
        if isinstance(variants, str):
            variants = [variants]
        if (
            not isinstance(variants, list)
            or not variants
            or any(not isinstance(text, str) or not text.strip() for text in variants)
        ):
            raise ValueError(f"{label}: text must contain at least one utterance")
        previous = float(time)
        turns.append(Turn(previous, random.choice(variants)))
    return Conversation(identifier, seed, tuple(turns))


class Replay:
    def __init__(self, session: Session, conversation: Conversation) -> None:
        self._session = session
        self._turns = conversation.turns
        self._index = 0
        self._time = 0.0

    def advance(self, elapsed: float) -> Iterator[tuple[Turn, Reply]]:
        if not isfinite(elapsed) or elapsed < self._time:
            raise ValueError("replay time must be finite and monotonic")
        self._time = elapsed
        while self._index < len(self._turns):
            turn = self._turns[self._index]
            if turn.time > elapsed:
                break
            reply = self._session.submit(turn.text)
            self._index += 1
            yield turn, reply
