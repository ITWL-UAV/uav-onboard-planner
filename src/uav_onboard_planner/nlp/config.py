from configparser import ConfigParser, SectionProxy
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, Self

from ..mission.instructions import InstructionType


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


@dataclass(frozen=True)
class PromptProfile:
    schema_version: int
    prompts: dict[InstructionType, Prompt]


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
    profile_keys = {"schema_version", *kinds}
    if (
        not isinstance(data, dict)
        or not profile_keys <= data.keys()
        or data.keys() - profile_keys - {"json_extraction", "constraints"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError(
            f"{path}: expected schema_version 1 and four instruction types"
        )

    separated = "json_extraction" in data
    extraction = data.get("json_extraction", {})
    constraints = data.get("constraints", {})
    extractable = set(kinds) - {"SYSTEM"}
    if not isinstance(extraction, dict) or (
        separated and extraction.keys() != extractable
    ):
        raise ValueError(
            f"{path}: json_extraction must cover GENERAL_INSTRUCTION, USER_INSTRUCTION and USER_PROMPT"
        )
    if (
        not isinstance(constraints, dict)
        or constraints.keys() - extractable
        or ("constraints" in data and not separated)
    ):
        raise ValueError(f"{path}: invalid constraints section")

    section_keys = {"source", "default_text"}
    if not separated:
        section_keys.add("fields")
    prompts: dict[InstructionType, Prompt] = {}
    for kind in kinds:
        section = data[kind]
        source = "profile" if kind in ("SYSTEM", "GENERAL_INSTRUCTION") else "operator"
        if (
            not isinstance(section, dict)
            or set(section) != section_keys
            or section["source"] != source
        ):
            raise ValueError(f"{path}: invalid {kind} section")

        default = section["default_text"]
        if source == "profile":
            if not isinstance(default, str) or not default.strip():
                raise ValueError(f"{path}: {kind}.default_text must be nonempty")
        elif default is not None:
            raise ValueError(f"{path}: {kind}.default_text must be null")

        definitions = extraction.get(kind, {}) if separated else section["fields"]
        if not isinstance(definitions, dict) or (kind != "SYSTEM" and not definitions):
            raise ValueError(f"{path}: {kind}.fields must define at least one field")
        if kind in constraints:
            if "constraints" in definitions:
                raise ValueError(
                    f"{path}: duplicate field definition {kind}.constraints"
                )
            definitions = {**definitions, "constraints": constraints[kind]}
        description_key = "question" if separated else "meaning"
        prompt_fields: dict[str, Field] = {}
        for name, field in definitions.items():
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
    return PromptProfile(data["schema_version"], prompts)
