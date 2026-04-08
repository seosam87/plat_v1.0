"""LLM pricing constants and cost computation utilities."""
from decimal import Decimal

PRICING = {
    "claude-haiku-4-5-20251001": {
        "input_per_mtok": Decimal("1.00"),
        "output_per_mtok": Decimal("5.00"),
    },
}


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Compute cost in USD for a given model and token counts.

    Args:
        model: Model ID string (must be in PRICING dict).
        input_tokens: Number of input/prompt tokens.
        output_tokens: Number of output/completion tokens.

    Returns:
        Cost in USD as Decimal quantized to 6 decimal places.
        Returns Decimal("0.000000") for unknown models.
    """
    p = PRICING.get(model)
    if not p:
        return Decimal("0.000000")
    cost = (
        Decimal(input_tokens) * p["input_per_mtok"]
        + Decimal(output_tokens) * p["output_per_mtok"]
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))
