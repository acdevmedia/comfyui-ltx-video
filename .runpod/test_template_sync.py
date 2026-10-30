"""Check template defaults, Hub inputs, tests and environment documentation agree."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT / '.runpod/template-source.json').read_text())
template = json.loads((ROOT / 'config/runpod-template.json').read_text())
hub = json.loads((ROOT / '.runpod/hub.json').read_text())
tests = json.loads((ROOT / '.runpod/tests.json').read_text())
documentation = (ROOT / 'docs/runpod-environment.md').read_text()
entries = {entry['key']: entry for entry in hub['config']['env']}
assert len(entries) == len(hub['config']['env']), 'Duplicate Hub environment keys'
test_env = {entry['key']: entry['value'] for entry in tests['config']['env']}
assert template['env'] == source['env']
assert template['name'] == source['templateName']
assert template['isPublic'] == source['isPublic']
assert template['imageName'] == source['imageName']
assert template['containerDiskInGb'] == hub['config']['containerDiskInGb'] == source['containerDiskInGb']
assert template['ports'] == source['ports']
for key, expected in source['env'].items():
    entry = entries[key]
    actual = entry.get('value', entry.get('input', {}).get('default'))
    if isinstance(actual, bool):
        actual = str(actual).lower()
    assert str(actual) == expected, (key, actual, expected)
    assert test_env[key] == expected, key
    assert f'### `{key}`' in documentation, key
    assert f'Default: `{expected}`.' in documentation, key
    assert f'{key}=' in (ROOT / '.env.example').read_text(), key
    if '{{ RUNPOD_SECRET_' in expected:
        assert entry['value'] == expected, 'Secret mapping must remain a reference'
assert entries['PORT']['value'] == '8000'
assert entries['PORT_HEALTH']['value'] == '8001'
print(f'PASS: {len(source["env"])} template variables match Hub defaults, test settings, examples and documentation.')
