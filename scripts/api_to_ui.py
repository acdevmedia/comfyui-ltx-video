#!/usr/bin/env python3
"""Turn an API prompt from v2v_graphs.py into a UI workflow offline, from the schemas saved with the profile."""
import copy

PRIMITIVES = {'INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO'}


def fields(schema, values, prefix=''):
    """(input name, spec, value, is widget) in the order the frontend expects them."""
    for group in ('required', 'optional'):
        for name, spec in schema.get(group, {}).items():
            name = prefix + name
            kind = spec[0]
            options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if kind == 'COMFY_DYNAMICCOMBO_V3':
                value = values.get(name, options['options'][0]['key'])
                yield name, ['COMBO', {'options': [o['key'] for o in options['options']]}], value, True
                choice = next(o for o in options['options'] if o['key'] == value)
                yield from fields(choice['inputs'], values, name + '.')
            elif kind == 'COMFY_AUTOGROW_V3':
                template = next(iter(options['template']['input']['required'].values()))
                for key, value in values.items():
                    if key.startswith(name + '.'):
                        yield key, template, value, False
            else:
                widget = not options.get('forceInput') and (isinstance(kind, list) or options.get('widgetType', kind) in PRIMITIVES)
                if name in values:
                    value = values[name]
                elif 'default' in options:
                    value = options['default']
                elif isinstance(kind, list):
                    value = kind[0] if kind else ''
                elif kind == 'COMBO':
                    value = options.get('options', [''])[0] if options.get('options') else ''
                else:
                    value = {'INT': 0, 'FLOAT': 0.0, 'STRING': '', 'BOOLEAN': False}.get(options.get('widgetType', kind))
                if group == 'optional' and name not in values and not widget:
                    continue
                if options.get('hidden'):
                    continue
                yield name, spec, value, widget


def to_ui(prompt, title, schemas):
    api = copy.deepcopy(prompt)
    data = {'id': title, 'last_node_id': max(map(int, api)), 'last_link_id': 0, 'nodes': [], 'links': [], 'groups': [], 'config': {},
            'extra': {'ds': {'scale': 0.75, 'offset': [20, 70]}}, 'version': 0.4}
    nodes, pending = {}, []
    for order, (key, source) in enumerate(api.items()):
        typ = source['class_type']
        schema = schemas[typ]
        node = {'id': int(key), 'type': typ, 'pos': [(order % 6) * 350, (order // 6) * 300], 'size': [310, 160], 'flags': {}, 'order': order, 'mode': 0,
                'inputs': [], 'outputs': [], 'properties': {'Node name for S&R': typ}, 'widgets_values': []}
        title_text = source.get('_meta', {}).get('title')
        if title_text:
            node['title'] = title_text
        for field, spec, value, widget in fields(schema['input'], source['inputs']):
            options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            kind = spec[0]
            slot = {'name': field, 'type': 'COMBO' if isinstance(kind, list) else kind, 'link': None}
            if widget:
                slot['widget'] = {'name': field}
            node['inputs'].append(slot)
            linked = isinstance(value, list)
            if widget:
                fallback = options.get('default', 0 if kind in ('INT', 'FLOAT') else '' if kind == 'STRING' else False if kind == 'BOOLEAN' else kind[0] if isinstance(kind, list) and kind else '')
                node['widgets_values'].append(fallback if linked else value)
                if options.get('control_after_generate'):
                    node['widgets_values'].append('fixed')
            if linked:
                pending.append((node, len(node['inputs']) - 1, value))
        for index, kind in enumerate(schema.get('output', [])):
            node['outputs'].append({'name': schema.get('output_name', schema['output'])[index], 'type': kind, 'links': []})
        nodes[int(key)] = node
        data['nodes'].append(node)
    for node, slot, value in pending:
        source, out = int(value[0]), value[1]
        link = len(data['links']) + 1
        kind = nodes[source]['outputs'][out]['type']
        data['links'].append([link, source, out, node['id'], slot, kind])
        node['inputs'][slot]['link'] = link
        nodes[source]['outputs'][out]['links'].append(link)
    data['last_link_id'] = len(data['links'])
    return data
