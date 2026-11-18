from configparser import ConfigParser, SectionProxy
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Self


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
    import yaml

    try:
        data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: invalid prompt YAML") from error
    if (
        not isinstance(data, dict)
        or set(data) != {"system"}
        or not isinstance(data["system"], str)
        or not data["system"].strip()
    ):
        raise ValueError(f"{path}: expected a nonempty 'system' prompt")
    return data["system"]
