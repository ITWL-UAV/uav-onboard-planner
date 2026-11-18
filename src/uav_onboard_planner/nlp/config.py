from collections.abc import Mapping
from configparser import ConfigParser, SectionProxy
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, Self

from ..mission.instructions import FieldValue, InstructionType


@dataclass(frozen=True)
class ModelConfig:
    model: str
    revision: str
    device: str
    dtype: str
    context_size: int

    def __post_init__(self) -> None:
        if not self.model or not self.revision or not self.device:
            raise ValueError("model, revision and device must be set")
        if self.context_size < 1:
            raise ValueError("context_size must be positive")

    @classmethod
    def _section(cls, path: Path, name: str) -> SectionProxy:
        parser = ConfigParser(interpolation=None)
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
        if parser.sections() != [name] or set(parser[name]) != {
            field.name for field in fields(cls)
        }:
            raise ValueError(f"{path}: invalid [{name}] fields")
        return parser[name]


@dataclass(frozen=True)
class SystemOneConfig(ModelConfig):
    max_new_tokens: int
    prompt_file: Path

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.dtype not in ("bfloat16", "float16"):
            raise ValueError("System One dtype must be bfloat16 or float16")
        if not 0 < self.max_new_tokens < self.context_size:
            raise ValueError("max_new_tokens must be positive and below context_size")

    @classmethod
    def load(cls, path: Path) -> Self:
        section = cls._section(path, "systemone")
        return cls(
            section["model"],
            section["revision"],
            section["device"],
            section["dtype"],
            int(section["context_size"]),
            int(section["max_new_tokens"]),
            path.parent / section["prompt_file"],
        )


@dataclass(frozen=True)
class EmbeddingConfig(ModelConfig):
    batch_size: int
    normalize: bool
    pooling: str

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.dtype not in ("float32", "bfloat16", "float16"):
            raise ValueError("unsupported embedding dtype")
        if self.batch_size < 1 or self.pooling not in ("cls", "mean"):
            raise ValueError(
                "embeddings require a positive batch_size and cls or mean pooling"
            )

    @classmethod
    def load(cls, path: Path) -> Self:
        section = cls._section(path, "embeddings")
        normalize = ConfigParser.BOOLEAN_STATES.get(section["normalize"].lower())
        if normalize is None:
            raise ValueError("normalize must be a boolean")
        return cls(
            section["model"],
            section["revision"],
            section["device"],
            section["dtype"],
            int(section["context_size"]),
            int(section["batch_size"]),
            normalize,
            section["pooling"],
        )


def load_system_prompt(path: Path) -> str:
    return _legacy_prompt(path, _load_prompt_yaml(path))


def _load_prompt_yaml(path: Path) -> object:
    import yaml

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: invalid prompt YAML") from error


def _legacy_prompt(path: Path, data: object) -> str:
    if (
        not isinstance(data, dict)
        or set(data) != {"system"}
        or not isinstance(data["system"], str)
        or not data["system"].strip()
    ):
        raise ValueError(f"{path}: expected a nonempty 'system' prompt")
    return data["system"]


@dataclass(frozen=True)
class Field:
    question: str
    type: Literal["text", "text_list"]
    required: bool
    embed: bool


@dataclass(frozen=True)
class Prompt:
    default_text: str | None
    fields: dict[str, Field]
    default_fields: dict[str, FieldValue] | None = None


@dataclass(frozen=True)
class PromptProfile:
    schema_version: int
    prompts: dict[InstructionType, Prompt]


def parse_fields(
    definitions: Mapping[str, Field], payload: object
) -> dict[str, FieldValue]:
    if not isinstance(payload, dict) or any(
        not isinstance(name, str) for name in payload
    ):
        raise ValueError("oczekiwano obiektu z kluczami tekstowymi")
    unknown = set(payload) - definitions.keys()
    if unknown:
        raise ValueError(f"nieznane pola: {', '.join(sorted(unknown))}")

    values: dict[str, FieldValue] = {}
    for name, field in definitions.items():
        value = payload.get(name)
        if value is None:
            continue
        if field.type == "text" and isinstance(value, str):
            if value.strip():
                values[name] = value.strip()
        elif field.type == "text_list" and isinstance(value, list):
            if any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f"nieprawidłowe pole: {name}")
            if value:
                values[name] = tuple(item.strip() for item in value)
        else:
            raise ValueError(f"nieprawidłowe pole: {name}")
    return values


def load_prompt(path: Path) -> PromptProfile | str:
    data = _load_prompt_yaml(path)
    if isinstance(data, dict) and set(data) == {"system"}:
        return _legacy_prompt(path, data)

    kinds: tuple[InstructionType, ...] = (
        "SYSTEM",
        "GENERAL_INSTRUCTION",
        "USER_INSTRUCTION",
        "USER_PROMPT",
    )
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", *kinds}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError(
            f"{path}: expected schema_version 1 and four instruction types"
        )

    section_keys = {"source", "default_text"}
    with_fields = section_keys | {"fields"}
    prompts: dict[InstructionType, Prompt] = {}
    for kind in kinds:
        section = data[kind]
        source = "profile" if kind in ("SYSTEM", "GENERAL_INSTRUCTION") else "operator"
        expected = [with_fields]
        if kind == "SYSTEM":
            expected.append(section_keys)
        if kind == "GENERAL_INSTRUCTION":
            expected.append(section_keys | {"default_fields"})
        if (
            not isinstance(section, dict)
            or set(section) not in expected
            or section["source"] != source
        ):
            raise ValueError(f"{path}: invalid {kind} section")

        default = section["default_text"]
        if source == "profile":
            if not isinstance(default, str) or not default.strip():
                raise ValueError(f"{path}: {kind}.default_text must be nonempty")
        elif default is not None:
            raise ValueError(f"{path}: {kind}.default_text must be null")

        definitions = section.get("fields", {})
        if not isinstance(definitions, dict) or (
            source == "operator" and not definitions
        ):
            raise ValueError(f"{path}: {kind}.fields must define at least one field")
        prompt_fields: dict[str, Field] = {}
        for name, field in definitions.items():
            description_key = (
                "question"
                if isinstance(field, dict) and "question" in field
                else "meaning"
            )
            if (
                not isinstance(name, str)
                or not name.strip()
                or name == "question"
                or not isinstance(field, dict)
                or set(field) != {description_key, "type", "required", "embed"}
                or not isinstance(field[description_key], str)
                or not field[description_key].strip()
                or field["type"] not in ("text", "text_list")
                or type(field["required"]) is not bool
                or type(field["embed"]) is not bool
            ):
                raise ValueError(f"{path}: invalid field definition {kind}.{name}")
            prompt_fields[name] = Field(
                field[description_key], field["type"], field["required"], field["embed"]
            )
        prompts[kind] = Prompt(default, prompt_fields)

    general_section = data["GENERAL_INSTRUCTION"]
    if "default_fields" in general_section:
        general = prompts["GENERAL_INSTRUCTION"]
        instruction_fields = prompts["USER_INSTRUCTION"].fields
        label = f"{path}: GENERAL_INSTRUCTION.default_fields"
        try:
            defaults = parse_fields(
                instruction_fields, general_section["default_fields"]
            )
        except ValueError as error:
            raise ValueError(f"{label}: {error}") from error
        missing = [
            name
            for name, field in instruction_fields.items()
            if field.required and name not in defaults
        ]
        if missing:
            raise ValueError(f"{label}: missing required fields: {', '.join(missing)}")
        prompts["GENERAL_INSTRUCTION"] = Prompt(
            general.default_text, instruction_fields, defaults
        )
    return PromptProfile(data["schema_version"], prompts)
