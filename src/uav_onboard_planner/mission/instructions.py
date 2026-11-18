from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

type InstructionType = Literal[
    "SYSTEM", "GENERAL_INSTRUCTION", "USER_INSTRUCTION", "USER_PROMPT"
]
type OperatorInstruction = Literal["USER_INSTRUCTION", "USER_PROMPT"]
type FieldValue = str | tuple[str, ...]


@dataclass(frozen=True)
class Instruction:
    text: str
    fields: Mapping[str, FieldValue]


class Mission:
    def __init__(self, system: Instruction, general: Instruction) -> None:
        self.system = system
        self.general = general
        self._user: Instruction | None = None
        self._changes: list[Instruction] = []

    @property
    def user(self) -> Instruction | None:
        return self._user

    @property
    def active(self) -> Instruction:
        return self._user if self._user is not None else self.general

    @property
    def changes(self) -> tuple[Instruction, ...]:
        return tuple(self._changes)

    @property
    def next_instruction(self) -> OperatorInstruction:
        return "USER_INSTRUCTION" if self._user is None else "USER_PROMPT"

    def accept(self, instruction: Instruction) -> None:
        if self._user is None:
            self._user = instruction
        else:
            self._changes.append(instruction)
