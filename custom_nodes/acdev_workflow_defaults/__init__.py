"""Register the workflow controls with ComfyUI's extension loader.

Seeds (shared with the H3 and WAN bundles): web/main.js randomizes seed widgets before
every queue in the UI. API jobs never run that script, so a seed of 0 in a queued prompt
means "pick one": this prompt hook replaces it with a fresh random seed on the server.
"""
import logging
import re
import secrets

WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

SEED_INPUT = re.compile(r"(^|_)seed$")
MAX_JS_SAFE = 2**53 - 1  # same range as the UI, so API and UI seeds look alike


def randomize_zero_seeds(json_data):
    """Replace literal 0 seeds (API default) with random ones; linked and non-zero seeds are untouched."""
    prompt = json_data.get("prompt") if isinstance(json_data, dict) else None
    if not isinstance(prompt, dict):
        return json_data
    for node_id, node in prompt.items():
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict):
            continue
        for name, value in list(inputs.items()):
            if SEED_INPUT.search(name) and type(value) is int and value == 0:
                inputs[name] = secrets.randbelow(MAX_JS_SAFE) + 1
                logging.info("[seed] node %s %s: 0 -> %s", node_id, name, inputs[name])
    return json_data


try:
    from server import PromptServer
    PromptServer.instance.add_on_prompt_handler(randomize_zero_seeds)
except (ImportError, AttributeError):  # imported outside a running ComfyUI (tests)
    pass
