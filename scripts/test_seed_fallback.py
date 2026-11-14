#!/usr/bin/env python3
"""API seed fallback: literal 0 seeds become random, everything else is untouched."""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("defaults", root / "custom_nodes/acdev_workflow_defaults/__init__.py")
defaults = importlib.util.module_from_spec(spec)
spec.loader.exec_module(defaults)

prompt = {"1": {"class_type": "RandomNoise", "inputs": {"noise_seed": 0}},
          "2": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 0}},
          "3": {"class_type": "KSampler", "inputs": {"seed": ["1", 0]}},
          "4": {"class_type": "Primitive", "inputs": {"value": 0, "seed_mode": 0}}}
first = defaults.randomize_zero_seeds({"prompt": prompt})["prompt"]
value = first["1"]["inputs"]["noise_seed"]
assert type(value) is int and 1 <= value <= 2**53 - 1, value
assert first["2"]["inputs"] == {"seed": 42, "steps": 0}, "non-zero seeds and other zero inputs are kept"
assert first["3"]["inputs"]["seed"] == ["1", 0], "linked seeds are kept"
assert first["4"]["inputs"] == {"value": 0, "seed_mode": 0}, "only *seed inputs are changed"
again = defaults.randomize_zero_seeds({"prompt": {"1": {"inputs": {"noise_seed": 0}}}})["prompt"]["1"]["inputs"]["noise_seed"]
assert again != value, "each queued job gets its own seed"
assert defaults.randomize_zero_seeds({"no_prompt": True}) == {"no_prompt": True}
print("PASS: API seed 0 is randomized server-side; set seeds, linked seeds and other inputs are untouched.")
