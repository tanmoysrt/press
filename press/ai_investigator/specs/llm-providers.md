# LLM Providers

AI Ops can use OpenAI, Anthropic, or an Anthropic-compatible endpoint such as Qwen.

Provider configuration is stored in `Press Settings`, not hardcoded in code. Secrets must use password fields or encrypted site config values.

---

## Press Settings Fields

Add these fields to existing `Press Settings`:

```
ai_ops_enabled: Check
ai_ops_default_provider: Select [OpenAI, Anthropic, Anthropic Compatible]
ai_ops_default_model: Data

ai_ops_openai_api_key: Password
ai_ops_openai_base_url: Data
ai_ops_openai_default_model: Data

ai_ops_anthropic_api_key: Password
ai_ops_anthropic_base_url: Data
ai_ops_anthropic_default_model: Data
ai_ops_anthropic_default_opus_model: Data
ai_ops_anthropic_default_sonnet_model: Data
ai_ops_anthropic_default_haiku_model: Data
ai_ops_anthropic_custom_headers_json: JSON

ai_ops_request_timeout_seconds: Int
ai_ops_max_output_tokens: Int
```

`ai_ops_anthropic_custom_headers_json` stores static headers attached to every Anthropic-compatible request. Do not put secrets in this JSON unless the field is encrypted; prefer password fields for secrets.

---

## Example: Qwen via Anthropic-Compatible Endpoint

Equivalent runtime config:

```json
{
  "model": "opus",
  "env": {
    "ANTHROPIC_BASE_URL": "http://15.206.91.192:8080",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "qwen3.6-27b-fp8",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "qwen3.6-27b-fp8",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "qwen3.6-27b-fp8"
  }
}
```

Stored in `Press Settings` as:

```json
{
  "ai_ops_default_provider": "Anthropic Compatible",
  "ai_ops_default_model": "opus",
  "ai_ops_anthropic_base_url": "http://15.206.91.192:8080",
  "ai_ops_anthropic_default_opus_model": "qwen3.6-27b-fp8",
  "ai_ops_anthropic_default_sonnet_model": "qwen3.6-27b-fp8",
  "ai_ops_anthropic_default_haiku_model": "qwen3.6-27b-fp8",
  "ai_ops_anthropic_custom_headers_json": {
    "X-Provider": "qwen"
  }
}
```

---

## Runtime Resolution

`press/ai_investigator/llm.py` should expose:

```python
def get_llm_config() -> dict:
    """Load provider settings, decrypt secrets, and return normalized config."""

def get_client():
    """Return a provider client for the selected Press Settings provider."""
```

Resolution rules:
- `OpenAI` uses OpenAI API-compatible client settings.
- `Anthropic` uses Anthropic API settings.
- `Anthropic Compatible` uses Anthropic request shape with custom `ai_ops_anthropic_base_url`, model aliases, and custom headers.
- `ai_ops_default_model = opus|sonnet|haiku` resolves through Anthropic model alias fields.
- explicit non-alias model names are passed through as-is.
- custom headers are merged into every provider request after redaction/audit filtering.

---

## Guardrails

- Never return API keys or custom auth headers to the model or UI.
- Redact provider settings from audit logs.
- Validate base URLs before saving.
- Require System Manager for reading or updating AI Ops fields in `Press Settings`.
- Store request/response metadata in audit logs, not full prompts by default.
