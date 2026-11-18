import json
from collections.abc import Callable
from importlib import import_module

from .config import (
    EmbeddingConfig,
    ModelConfig,
    PromptProfile,
    SystemOneConfig,
    load_prompt,
)
from .session import Embeddings

_ANSWER_FORMAT = {
    "text": "Reply with the answer only, in a short phrase.",
    "text_list": "Write one item per line without bullets.",
    "text_map": (
        "Write one role: value per line. For a list, write role[]: value once per item."
    ),
}


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


def _extract_fields(context: str, generate: Callable[[str], str]) -> dict[str, object]:
    request = json.loads(context)
    fields = request.pop("fields")
    if request.get("instruction") == "USER_INSTRUCTION":
        request.pop("active_instruction", None)
    message = request.pop("operator_message", "")
    mission = json.dumps(request, ensure_ascii=False)
    result: dict[str, object] = {}
    for name, field in fields.items():
        kind = field["type"]
        answer = generate(
            f"Mission context:\n{mission}\n\nOperator: {message}\n\n"
            f"Question: {field['question']}\n{_ANSWER_FORMAT[kind]}\n"
            "If the information is absent, write N/A. If the operator must clarify, "
            "write Clarify: followed by the question."
        ).strip()
        if not answer or answer.casefold() == "n/a":
            continue
        if answer.startswith("Clarify:"):
            question = answer.removeprefix("Clarify:").strip()
            if question and field.get("required", True):
                return {"question": question}
            continue
        if kind == "text":
            result[name] = answer
        else:
            lines = [line.strip() for line in answer.splitlines() if line.strip()]
            result[name] = _named_answers(lines) if kind == "text_map" else lines
    return result


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
        return _extract_fields(context, self._generate)

    def _generate(self, message: str) -> str:
        runtime = self._runtime
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
        if input_size + self._settings.max_new_tokens > self._settings.context_size:
            raise ValueError("polecenie i jego kontekst przekraczają context_size")
        with runtime.torch.inference_mode():
            result = runtime.model.generate(
                **tokens, max_new_tokens=self._settings.max_new_tokens, do_sample=False
            )
        return runtime.tokenizer.decode(
            result[0, input_size:], skip_special_tokens=True
        )


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
