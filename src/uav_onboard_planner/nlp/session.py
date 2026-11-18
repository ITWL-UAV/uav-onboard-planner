import json
from dataclasses import dataclass
from math import isfinite
from typing import Literal, Protocol


@dataclass(frozen=True)
class Embeddings:
    model: str
    revision: str
    vectors: tuple[tuple[float, ...], ...]

    @property
    def dimension(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


class Interpreter(Protocol):
    def interpret(self, context: str) -> object: ...


class Encoder(Protocol):
    def encode(self, texts: tuple[str, ...]) -> Embeddings: ...


@dataclass(frozen=True)
class Reply:
    instruction: Literal["USER_INSTRUCTION", "USER_PROMPT"] | None = None
    sites: tuple[str, ...] = ()
    embeddings: Embeddings | None = None
    question: str | None = None

    def to_json(self) -> str:
        if self.embeddings is None:
            return json.dumps(
                {"schema_version": 1, "question": self.question}, ensure_ascii=False
            )
        return json.dumps(
            {
                "schema_version": 1,
                "instruction": self.instruction,
                "draft": {"task": "inspection", "sites": self.sites},
                "embeddings": {
                    "model": self.embeddings.model,
                    "revision": self.embeddings.revision,
                    "dimension": self.embeddings.dimension,
                    "fields": {"sites": self.embeddings.vectors},
                },
            },
            ensure_ascii=False,
            allow_nan=False,
        )


class Session:
    def __init__(self, interpreter: Interpreter, encoder: Encoder) -> None:
        self._interpreter = interpreter
        self._encoder = encoder
        self._original_instruction: str | None = None
        self._sites: tuple[str, ...] = ()
        self._clarification: tuple[str, str] | None = None

    @property
    def user_instruction(self) -> str | None:
        return self._original_instruction

    def submit(self, text: str) -> Reply:
        if not text.strip():
            raise ValueError("polecenie jest puste")
        proposal = self._interpreter.interpret(
            json.dumps(
                {
                    "user_instruction": self.user_instruction,
                    "current_sites": self._sites,
                    "pending_clarification": self._clarification,
                    "operator_message": text,
                },
                ensure_ascii=False,
            )
        )
        if isinstance(proposal, dict) and set(proposal) == {"question"}:
            question = proposal["question"]
            if isinstance(question, str) and question.strip():
                previous_text = self._clarification[0] if self._clarification else text
                self._clarification = (previous_text, question)
                return Reply(question=question)
        if (
            not isinstance(proposal, dict)
            or set(proposal) != {"sites"}
            or not isinstance(proposal["sites"], list)
            or not proposal["sites"]
            or any(
                not isinstance(site, str) or not site.strip()
                for site in proposal["sites"]
            )
        ):
            raise ValueError("model zwrócił nieprawidłowy szkic inspekcji")

        sites: tuple[str, ...] = tuple(site.strip() for site in proposal["sites"])
        if len(set(sites)) != len(sites):
            raise ValueError("szkic zawiera powtórzone miejsca")
        embeddings = self._encoder.encode(sites)
        if (
            len(embeddings.vectors) != len(sites)
            or not embeddings.dimension
            or any(
                len(vector) != embeddings.dimension or not all(map(isfinite, vector))
                for vector in embeddings.vectors
            )
        ):
            raise ValueError("enkoder zwrócił nieprawidłowe wektory")
        instruction: Literal["USER_INSTRUCTION", "USER_PROMPT"] = "USER_PROMPT"
        if self._original_instruction is None:
            instruction = "USER_INSTRUCTION"
            self._original_instruction = (
                self._clarification[0] if self._clarification else text
            )
        self._sites = sites
        self._clarification = None
        return Reply(instruction, sites, embeddings)
