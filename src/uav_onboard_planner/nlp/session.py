import json
from dataclasses import asdict, dataclass
from math import isfinite
from types import MappingProxyType
from typing import Protocol

from ..mission.instructions import FieldValue, Instruction, InstructionType, Mission
from .config import Prompt, PromptProfile

type Vector = tuple[float, ...]


@dataclass(frozen=True)
class Embeddings:
    model: str
    revision: str
    vectors: tuple[Vector, ...]

    @property
    def dimension(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


class Interpreter(Protocol):
    def interpret(self, context: str) -> object: ...


class Encoder(Protocol):
    def encode(self, texts: tuple[str, ...]) -> Embeddings: ...


@dataclass(frozen=True)
class Reply:
    instruction: InstructionType | None = None
    sites: tuple[str, ...] = ()
    embeddings: Embeddings | None = None
    question: str | None = None
    schema_version: int = 1
    draft: dict[str, FieldValue] | None = None
    vectors_by_field: dict[str, Vector | tuple[Vector, ...]] | None = None

    def to_json(self) -> str:
        data: dict[str, object] = {"schema_version": self.schema_version}
        if self.question is not None:
            data["question"] = self.question
        else:
            data["instruction"] = self.instruction
            data["draft"] = (
                self.draft
                if self.draft is not None
                else {"task": "inspection", "sites": self.sites}
            )
            if self.embeddings is not None:
                data["embeddings"] = {
                    "model": self.embeddings.model,
                    "revision": self.embeddings.revision,
                    "dimension": self.embeddings.dimension,
                    "fields": (
                        self.vectors_by_field
                        if self.vectors_by_field is not None
                        else {"sites": self.embeddings.vectors}
                    ),
                }
        return json.dumps(data, ensure_ascii=False, allow_nan=False)


def _question(proposal: object) -> str | None:
    if isinstance(proposal, dict) and set(proposal) == {"question"}:
        question = proposal["question"]
        if isinstance(question, str) and question.strip():
            return question.strip()
    return None


def _fields(prompt: Prompt, proposal: object) -> dict[str, FieldValue]:
    if not isinstance(proposal, dict) or any(
        not isinstance(name, str) for name in proposal
    ):
        raise ValueError("model musi zwrócić obiekt JSON z kluczami tekstowymi")
    unknown = set(proposal) - prompt.fields.keys()
    if unknown:
        raise ValueError(f"model zwrócił nieznane pola: {', '.join(sorted(unknown))}")

    values: dict[str, FieldValue] = {}
    for name, field in prompt.fields.items():
        value = proposal.get(name)
        if value is None:
            continue
        if field.type == "text" and isinstance(value, str):
            if value.strip():
                values[name] = value.strip()
        elif field.type == "text_list" and isinstance(value, list):
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"model zwrócił nieprawidłowe pole: {name}")
            if value:
                values[name] = tuple(item.strip() for item in value)
        else:
            raise ValueError(f"model zwrócił nieprawidłowe pole: {name}")
    return values


def _context(instruction: Instruction) -> dict[str, object]:
    return {"text": instruction.text, "fields": dict(instruction.fields)}


class Session:
    def __init__(
        self,
        interpreter: Interpreter,
        encoder: Encoder,
        profile: PromptProfile | None = None,
    ) -> None:
        self._interpreter = interpreter
        self._encoder = encoder
        self._profile = profile
        self._clarification: tuple[str, ...] = ()
        self._original_instruction: str | None = None
        self._sites: tuple[str, ...] = ()
        self.mission: Mission | None = None
        self.initial: tuple[Reply, ...] = ()
        if profile is not None:
            system, system_reply = self._default("SYSTEM", {})
            general, general_reply = self._default(
                "GENERAL_INSTRUCTION", {"system": _context(system)}
            )
            self.mission = Mission(system, general)
            self.initial = (system_reply, general_reply)

    @property
    def user_instruction(self) -> str | None:
        if self.mission is not None:
            user = self.mission.user
            return user.text if user is not None else None
        return self._original_instruction

    def submit(self, text: str) -> Reply:
        if not text.strip():
            raise ValueError("polecenie jest puste")
        if self.mission is not None:
            return self._submit(text, self.mission)
        return self._submit_legacy(text)

    def _ask(self, text: str, question: str) -> Reply:
        self._clarification += (text, question)
        return Reply(question=question)

    def _encode(self, texts: tuple[str, ...]) -> Embeddings:
        embeddings = self._encoder.encode(texts)
        if (
            len(embeddings.vectors) != len(texts)
            or not embeddings.model.strip()
            or not embeddings.revision.strip()
            or not embeddings.dimension
            or any(
                len(vector) != embeddings.dimension or not all(map(isfinite, vector))
                for vector in embeddings.vectors
            )
        ):
            raise ValueError("enkoder zwrócił nieprawidłowe wektory")
        return embeddings

    def _submit_legacy(self, text: str) -> Reply:
        proposal = self._interpreter.interpret(
            json.dumps(
                {
                    "user_instruction": self.user_instruction,
                    "current_sites": self._sites,
                    "pending_clarification": (
                        (self._clarification[0], self._clarification[-1])
                        if self._clarification
                        else None
                    ),
                    "operator_message": text,
                },
                ensure_ascii=False,
            )
        )
        question = _question(proposal)
        if question is not None:
            return self._ask(text, question)
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
        embeddings = self._encode(sites)
        instruction: InstructionType = "USER_PROMPT"
        if self._original_instruction is None:
            instruction = "USER_INSTRUCTION"
            self._original_instruction = (
                self._clarification[0] if self._clarification else text
            )
        self._sites = sites
        self._clarification = ()
        return Reply(instruction, sites, embeddings)

    def _default(
        self, kind: InstructionType, context: dict[str, object]
    ) -> tuple[Instruction, Reply]:
        assert self._profile is not None
        text = self._profile.prompts[kind].default_text
        assert text is not None
        reply = self._interpret(kind, text, context)
        if reply.draft is None:
            raise ValueError(f"{kind}: {reply.question}")
        return Instruction(text, MappingProxyType(reply.draft.copy())), reply

    def _submit(self, text: str, mission: Mission) -> Reply:
        reply = self._interpret(
            mission.next_instruction,
            text,
            {
                "system": _context(mission.system),
                "active_instruction": _context(mission.active),
                "accepted_changes": [_context(change) for change in mission.changes],
                "pending_clarification": self._clarification,
            },
        )
        if reply.question is not None:
            return self._ask(text, reply.question)
        assert reply.draft is not None
        original = self._clarification[0] if self._clarification else text
        mission.accept(Instruction(original, MappingProxyType(reply.draft.copy())))
        self._clarification = ()
        return reply

    def _interpret(
        self, kind: InstructionType, text: str, context: dict[str, object]
    ) -> Reply:
        assert self._profile is not None
        profile = self._profile
        prompt = profile.prompts[kind]
        proposal = self._interpreter.interpret(
            json.dumps(
                {
                    "instruction": kind,
                    "fields": {
                        name: asdict(field) for name, field in prompt.fields.items()
                    },
                    "operator_message"
                    if prompt.default_text is None
                    else "profile_text": text,
                    **context,
                },
                ensure_ascii=False,
            )
        )
        question = _question(proposal)
        if question is not None:
            return Reply(question=question, schema_version=profile.schema_version)
        draft = _fields(prompt, proposal)
        missing = [
            name
            for name, field in prompt.fields.items()
            if field.required and name not in draft
        ]
        if missing:
            return Reply(
                question=f"Czy możesz doprecyzować: {', '.join(missing)}?",
                schema_version=profile.schema_version,
            )

        texts = tuple(
            item
            for name, value in draft.items()
            if prompt.fields[name].embed
            for item in ((value,) if isinstance(value, str) else value)
        )
        embeddings = self._encode(texts) if texts else None
        vectors_by_field: dict[str, Vector | tuple[Vector, ...]] = {}
        if embeddings is not None:
            vectors = iter(embeddings.vectors)
            for name, value in draft.items():
                if prompt.fields[name].embed:
                    vectors_by_field[name] = (
                        next(vectors)
                        if isinstance(value, str)
                        else tuple(next(vectors) for _ in value)
                    )
        sites = draft.get("sites")
        return Reply(
            kind,
            sites if isinstance(sites, tuple) else (),
            embeddings,
            schema_version=profile.schema_version,
            draft=draft,
            vectors_by_field=vectors_by_field,
        )
