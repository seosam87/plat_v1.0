# Powered by Claude Haiku 4.5 — для апгрейда до Sonnet/Opus отредактируй
# ANTHROPIC_MODEL и пересобери (D-01 mandatory note)
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_MODEL_LABEL = "Claude Haiku 4.5"
INPUT_TOKEN_BUDGET = 2000
OUTPUT_TOKEN_BUDGET = 800
INPUT_CHAR_BUDGET = INPUT_TOKEN_BUDGET * 4  # 4 chars/token rule of thumb
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_TTL_SECONDS = 900  # 15 min per D-06
