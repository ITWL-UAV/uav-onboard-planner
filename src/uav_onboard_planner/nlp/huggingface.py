import json
import re
from collections.abc import Callable
from importlib import import_module
from itertools import islice, product
from string import ascii_uppercase

from .config import (
    EmbeddingConfig,
    ModelConfig,
    PromptProfile,
    SystemOneConfig,
    load_prompt,
)
from .session import Embeddings, Interpretation

type Options = tuple[str | None, ...]
type Choose = Callable[[str, Options], tuple[int, float]]


def _named_answers(lines: list[str]) -> dict[str, str | list[str]]:
    values: dict[str, str | list[str]] = {}
    for line in lines:
        role, separator, value = line.partition(":")
        role, value = role.strip(), value.strip()
        is_list = role.endswith("[]")
        if is_list:
            role = role.removesuffix("[]").strip()
        if not role or not separator or not value:
            raise ValueError(f"nieprawidłowa odpowiedź dla pola mapy: {line}")
        if is_list:
            items = values.setdefault(role, [])
            if not isinstance(items, list):
                raise ValueError(f"sprzeczny typ odpowiedzi dla roli {role}")
            items.append(value)
        elif role in values:
            raise ValueError(f"powtórzona rola w odpowiedzi: {role}")
        else:
            values[role] = value
    return values


def _extract_fields(context: str, choose: Choose) -> Interpretation:
    request = json.loads(context)
    fields = request.pop("fields")
    if request.get("instruction") == "USER_INSTRUCTION":
        request.pop("active_instruction", None)
    message = request.pop("operator_message", "")
    words = list(re.finditer(r"\S+", message))
    if len(words) > 60:
        raise ValueError(
            "User prompt is too long to rank its excerpts. Enter a shorter prompt."
        )
    options: Options = (
        None,
        *dict.fromkeys(
            message[first.start() : last.end()]
            for index, first in enumerate(words)
            for last in words[index:]
        ),
    )
    mission = json.dumps(request, ensure_ascii=False)
    result: dict[str, object] = {}
    confidence: dict[str, float] = {}
    for name, field in fields.items():
        kind = field["type"]
        index, score = choose(
            f"Mission context:\n{mission}\n\nOperator: {message}\n\n"
            f"Question: {field['question']}",
            options,
        )
        if not 0 <= index < len(options) or not 0 <= score <= 1:
            raise ValueError("System One returned an invalid choice or confidence")
        confidence[name] = score
        answer = options[index]
        if answer is None:
            continue
        if kind == "text":
            result[name] = answer
        else:
            lines = [line.strip() for line in answer.splitlines() if line.strip()]
            result[name] = _named_answers(lines) if kind == "text_map" else lines
    return Interpretation(result, confidence)


class _Runtime:
    def __init__(self, settings: ModelConfig, *, generation: bool) -> None:
        self.torch = import_module("torch")
        transformers = import_module("transformers")
        hub = import_module("transformers.utils.hub")
        self.device = settings.device
        if self.device == "auto":
            if self.torch.cuda.is_available():
                self.device = "cuda"
            elif self.torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        config_file = hub.cached_file(
            settings.model, "config.json", revision=settings.revision
        )
        self.revision = hub.extract_commit_hash(config_file, None) or settings.revision
        config = transformers.AutoConfig.from_pretrained(
            settings.model, revision=self.revision
        )
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            settings.model, revision=self.revision
        )
        loader = transformers.AutoModel
        if generation:
            loader = (
                transformers.AutoModelForImageTextToText
                if getattr(config, "vision_config", None) is not None
                else transformers.AutoModelForCausalLM
            )
        self.model = (
            loader.from_pretrained(
                settings.model,
                revision=self.revision,
                config=config,
                dtype=settings.dtype,
                use_safetensors=True,
            )
            .to(self.device)
            .eval()
        )


class HuggingFaceSystemOne:
    def __init__(
        self, settings: SystemOneConfig, prompt: PromptProfile | str | None = None
    ) -> None:
        self._settings = settings
        if prompt is None:
            prompt = load_prompt(settings.prompt_file)
        self._legacy_prompt = prompt if isinstance(prompt, str) else None
        self._runtime = _Runtime(settings, generation=True)
        self._vocabulary = self._runtime.tokenizer.get_vocab()

    def interpret(self, context: str) -> object:
        if self._legacy_prompt is not None:
            request = json.loads(context)
            request["system"] = self._legacy_prompt
            request["fields"] = {
                "sites": {
                    "question": "Which sites should the operator's inspection cover, in order?",
                    "type": "text_list",
                }
            }
            context = json.dumps(request, ensure_ascii=False)
        return _extract_fields(context, self._choose)

    def _choose(self, message: str, options: Options) -> tuple[int, float]:
        runtime = self._runtime
        labels = list(
            islice(
                (
                    label
                    for size in (1, 2, 3)
                    for letters in product(ascii_uppercase, repeat=size)
                    if (label := "".join(letters)) in self._vocabulary
                ),
                len(options),
            )
        )
        if len(labels) != len(options):
            raise ValueError("Too many candidate excerpts. Enter a shorter prompt.")
        choices = "\n".join(
            f"{label}: {json.dumps(option, ensure_ascii=False) if option is not None else 'No answer in the operator message'}"
            for label, option in zip(labels, options, strict=True)
        )
        message = (
            f"{message}\n\nChoose the answer option. Return only its label.\n{choices}"
        )
        prompt = runtime.tokenizer.apply_chat_template(
            [{"role": "user", "content": message}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        tokens = runtime.tokenizer(
            prompt, add_special_tokens=False, return_tensors="pt"
        ).to(runtime.device)
        input_size = tokens["input_ids"].shape[-1]
        if input_size >= self._settings.context_size:
            raise ValueError(
                "The prompt and candidate excerpts exceed context_size. Enter a shorter prompt."
            )
        with runtime.torch.inference_mode():
            logits = runtime.model(**tokens, use_cache=False, logits_to_keep=1).logits[
                0, -1
            ]
            probabilities = (
                logits[[self._vocabulary[label] for label in labels]]
                .float()
                .softmax(dim=0)
            )
            index = probabilities.argmax().item()
            score = probabilities[index].item()
        return index, score


class HuggingFaceEncoder:
    def __init__(self, settings: EmbeddingConfig) -> None:
        self._settings = settings
        self._runtime = _Runtime(settings, generation=False)

    def encode(self, texts: tuple[str, ...]) -> Embeddings:
        runtime = self._runtime
        settings = self._settings
        vectors: list[tuple[float, ...]] = []
        with runtime.torch.inference_mode():
            for start in range(0, len(texts), settings.batch_size):
                batch = list(texts[start : start + settings.batch_size])
                tokens = runtime.tokenizer(batch, padding=True, return_tensors="pt")
                if tokens["input_ids"].shape[-1] > settings.context_size:
                    raise ValueError("tekst do wektoryzacji przekracza context_size")
                tokens = tokens.to(runtime.device)
                hidden = runtime.model(**tokens).last_hidden_state.float()
                if settings.pooling == "cls":
                    pooled = hidden[:, 0]
                else:
                    mask = tokens["attention_mask"].unsqueeze(-1)
                    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
                if settings.normalize:
                    pooled = runtime.torch.nn.functional.normalize(pooled, dim=-1)
                vectors.extend(tuple(row) for row in pooled.cpu().tolist())
        return Embeddings(settings.model, runtime.revision, tuple(vectors))
