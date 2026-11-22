"""Known model prices (USD per million tokens), used to put `cost_usd` on every card.

Fireworks serverless prices as measured for the German bake-off (Nov 2026). Prices change:
pass `pricing=Pricing(...)` to `OpenAICompatibleLLM` to override.
"""

from easyvocab.models import Pricing

FIREWORKS_PRICING: dict[str, Pricing] = {
    "deepseek-v4p1-flash": Pricing(input_per_million=0.3, output_per_million=1.2, cached_input_per_million=0.006),
    "glm-5p3": Pricing(input_per_million=1.4, output_per_million=4.4, cached_input_per_million=0.26),
    "kimi-k3": Pricing(input_per_million=3.0, output_per_million=15.0, cached_input_per_million=0.3),
}
