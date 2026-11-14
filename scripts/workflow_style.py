"""Give the LTX workflows the same canvas as the Eros and H3 bundles without changing execution.

01 · Describe your shot   the prompt, pulled out of the controls panel into its own text box
<inputs>                  images, clips, audio (LTX's own labels, colours as Eros)
02 · Shot settings        the existing Filmmaker controls panel (negative prompt included)
03 · Your video / audio   the saver
"""
import re

from workflow_panels import flatten

PROMPT = ('01 · Describe your shot', '#28524d', '#172f2c')
INPUT = ('#334c63', '#1b2b3b')
PANEL = ('02 · Shot settings', '#484661', '#29283d')
OUTPUT = ('#3c5540', '#223025')
LOADERS = ('LoadImage', 'LoadAudio', 'LoadVideo', 'SphereLightManualNode')
RENAME = {'Opening Image': 'Starting image', 'Opening Frame': 'First frame', 'Closing Frame': 'Last frame',
          'Optional Opening Frame': 'Optional starting image'}
NOT_PROMPT = re.compile(r'negative|sampling timings', re.I)


def _panel(data):
    ids = {s['id'] for s in data.get('definitions', {}).get('subgraphs', [])}
    panels = [n for n in data['nodes'] if n['type'] in ids]
    return panels[0] if len(panels) == 1 else None


def _get(data, node, inp):
    """A panel field's value. LTX panels keep values by name, in subgraph input order."""
    named = node.get('widgets_values_named') or {}
    if inp['name'] in named:
        return named[inp['name']]
    return node['widgets_values'][_order(data, node).index(inp['name'])]


def _set(data, node, inp, value):
    order = _order(data, node)
    if inp['name'] in order and order.index(inp['name']) < len(node['widgets_values']):
        node['widgets_values'][order.index(inp['name'])] = value
    if 'widgets_values_named' in node:
        node['widgets_values_named'][inp['name']] = value


def _order(data, node):
    widget_names = {i['name'] for i in node['inputs'] if i.get('widget')}
    sub = next(s for s in data['definitions']['subgraphs'] if s['id'] == node['type'])
    return [i['name'] for i in sub['inputs'] if i['name'] in widget_names]


def _link_id(link):
    return link['id'] if isinstance(link, dict) else link[0]


def _new_link(data, origin, origin_slot, target, target_slot, typ):
    """Append a link in whichever format this workflow already uses (list or object)."""
    link_id = max([_link_id(l) for l in data['links']] + [data.get('last_link_id', 0)]) + 1
    if any(isinstance(l, dict) for l in data['links']):
        data['links'].append({'id': link_id, 'origin_id': origin['id'], 'origin_slot': origin_slot,
                              'target_id': target['id'], 'target_slot': target_slot, 'type': typ})
    else:
        data['links'].append([link_id, origin['id'], origin_slot, target['id'], target_slot, typ])
    data['last_link_id'] = link_id
    return link_id


def style_canvas(data):
    panel = _panel(data)
    if panel is None or any(n.get('title') == PANEL[0] for n in data['nodes']):
        return data  # nothing to style, or already styled
    try:
        before = flatten(data)
    except StopIteration:  # flatten() cannot read some LTX panels; the edits below are wiring-safe by construction
        before = None
    moved = []  # texts that now come from a different place (prompt panel, folded negative)
    nodes = {n['id']: n for n in data['nodes']}
    texts = [i for i in panel['inputs'] if i.get('type') == 'STRING']
    # Negative prompt lives in Shot settings, as on Eros: fold a separate "Avoid" text panel into it.
    for inp in texts:
        # Only a negative *field* can take the text; a plain negative socket keeps its own panel.
        if inp.get('widget') and 'negative' in (inp.get('label') or '').lower() and inp.get('link') is not None:
            link = next(l for l in data['links'] if _link_id(l) == inp['link'])
            source = nodes.get(link['origin_id'] if isinstance(link, dict) else link[1])
            if source and source['type'] == 'PrimitiveStringMultiline':
                moved.append(source['widgets_values'][0])
                _set(data, panel, inp, source['widgets_values'][0])
                data['links'] = [l for l in data['links'] if _link_id(l) != _link_id(link)]
                inp['link'] = None
                data['nodes'] = [n for n in data['nodes'] if n['id'] != source['id']]
    # The prompt gets its own panel, wired into the same field.
    prompt_input = next((i for i in texts if i.get('widget') and not NOT_PROMPT.search(i.get('label') or i['name']) and i.get('link') is None), None)
    prompt = None
    if prompt_input is not None:
        last = max(n['id'] for graph in [data] + data.get('definitions', {}).get('subgraphs', []) for n in graph.get('nodes', [])) + 1
        prompt = {'id': last, 'type': 'PrimitiveStringMultiline', 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [],
                  'outputs': [{'name': 'STRING', 'type': 'STRING', 'links': []}], 'properties': {'Node name for S&R': 'PrimitiveStringMultiline'},
                  'widgets_values': [_get(data, panel, prompt_input)]}
        moved.append(prompt['widgets_values'][0])
        data['nodes'].append(prompt)
        data['last_node_id'] = max(data.get('last_node_id', 0), last)
        link_id = _new_link(data, prompt, 0, panel, panel['inputs'].index(prompt_input), 'STRING')
        prompt['outputs'][0]['links'].append(link_id)
        prompt_input['link'] = link_id
    # Titles, colours and a left-to-right layout matching Eros.
    loaders = [n for n in data['nodes'] if n['type'] in LOADERS]
    savers = [n for n in data['nodes'] if n['type'].startswith('Save') or n['type'] == 'PreviewAudio']
    height = max(panel['size'][1], 380 + 540 * len(loaders))
    for node in data['nodes']:
        if node is prompt:
            node.update(title=PROMPT[0], color=PROMPT[1], bgcolor=PROMPT[2], pos=[0, 100], size=[480, 220])
        elif node['type'] == 'PrimitiveStringMultiline':  # LTX's separate negative text (feeds a socket)
            node.update(title='Negative prompt', color=PROMPT[1], bgcolor=PROMPT[2], pos=[0, 380 + 540 * len(loaders)], size=[480, 300])
        elif node in loaders:
            k = loaders.index(node)
            node.update(title=RENAME.get(node.get('title'), node.get('title') or node['type']), color=INPUT[0], bgcolor=INPUT[1],
                        pos=[0, 380 + 540 * k], size=[480, 520 if len(loaders) > 1 else 680])
        elif node is panel:
            node.update(title=PANEL[0], color=PANEL[1], bgcolor=PANEL[2], pos=[540, 100])
        elif node in savers:
            k = savers.index(node)
            audio = 'Audio' in node['type'] and 'Video' not in node['type']
            node.update(title=('03 · Your audio' if audio else '03 · Your video') if k == 0 else node.get('title'),
                        color=OUTPUT[0], bgcolor=OUTPUT[1], pos=[600 + panel['size'][0], 100 + 560 * k])
    data.setdefault('extra', {}).pop('ds', None)  # let the frontend fit the canvas to the window
    if before is None:
        return data
    after = flatten(data)
    assert set(after) == set(before), 'Styling changed workflow execution'
    for key, (typ, widgets, inputs) in before.items():
        a_typ, a_widgets, a_inputs = after[key]
        assert (typ, widgets) == (a_typ, a_widgets) and set(inputs) == set(a_inputs), f'Styling changed {key}'
        for name, value in inputs.items():
            # flatten() cannot read some panel values (None); they may only become the moved texts.
            assert a_inputs[name] == value or (value == ('value', None) and a_inputs[name][0] == 'value' and a_inputs[name][1] in moved), f'Styling changed {key}.{name}'
    return data
