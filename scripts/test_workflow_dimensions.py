"""Check that render dimensions resolve to editable controls on the main canvas."""
import copy
import json
import math
from pathlib import Path
from workflow_dimensions import LATENTS, apply_dimensions, fit_expression, link_parts
ROOT=Path(__file__).resolve().parents[1]

def inspect(data):
    definitions={g['id']:g for g in data.get('definitions',{}).get('subgraphs',[])}
    contexts=[]
    def walk(g,parents):
        contexts.append((g,parents))
        for n in g['nodes']:
            if n['type'] in definitions:walk(definitions[n['type']],parents+[(g,n)])
    walk(data,[])
    def proxy_widget(node,name):
        sub=definitions[node['type']]
        idx=next(i for i,x in enumerate(sub['inputs']) if x['name']==name)
        link=next(link_parts(l) for l in sub['links'] if link_parts(l)[1:3]==[-10,idx])
        inner=next(n for n in sub['nodes'] if n['id']==link[3])
        names=[i['name'] for i in inner['inputs'] if i.get('widget')]
        return inner,names.index(inner['inputs'][link[4]]['name'])
    def widget(node,name):
        if name in node.get('widgets_values_named',{}):return node['widgets_values_named'][name]
        names=[i['name'] for i in node.get('inputs',[]) if i.get('widget')]
        if not node.get('widgets_values') and node.get('properties',{}).get('proxyWidgets'):
            inner,index=proxy_widget(node,name)
            return inner['widgets_values'][index]
        return node['widgets_values'][names.index(name)]
    def resolve(g,parents,node,name,depth=0):
        assert depth<40,'dimension wiring cycle'
        inp=next(i for i in node['inputs'] if i['name']==name)
        if inp.get('link') is None:
            assert g is data,(node['id'],name,'dimension is hidden inside a subgraph')
            assert inp.get('widget'),(node['id'],name,'missing editable widget')
            return node,name,widget(node,name),1
        link=next(link_parts(l) for l in g['links'] if link_parts(l)[0]==inp['link'])
        if link[1]==-10:
            parent,inst=parents[-1]
            return resolve(parent,parents[:-1],inst,g['inputs'][link[2]]['name'],depth+1)
        source=next(n for n in g['nodes'] if n['id']==link[1])
        if source['type']=='PrimitiveInt':
            v=next((i for i in source.get('inputs',[]) if i['name']=='value' and i.get('link') is not None),None)
            if v:return resolve(g,parents,source,'value',depth+1)
            assert g is data,(source['id'],'dimension comes from a hidden primitive')
            return source,'value',source['widgets_values'][0],1
        if source['type']=='GetImageSize':
            image_link=next(link_parts(l) for l in g['links'] if link_parts(l)[0]==source['inputs'][0]['link'])
            resize=next(n for n in g['nodes'] if n['id']==image_link[1])
            assert resize['type']=='ResizeImageMaskNode',resize['type']
            axis='width' if link[2]==0 else 'height'
            return resolve(g,parents,resize,'resize_type.'+axis,depth+1)
        if source['type']=='ComfyMathExpression' and source.get('title','').startswith('Fit Frame'):
            # The panel sets the area; the image fills in the proportions.
            return resolve(g,parents,source,'values.a' if source['title'].endswith('Width') else 'values.b',depth+1)
        if source['type']=='ComfyMathExpression':
            assert source['widgets_values'][0]=='a/2',source['widgets_values']
            control,name,value,factor=resolve(g,parents,source,'values.a',depth+1)
            return control,name,value/2,factor/2
        if source['type']=='Reroute':return resolve(g,parents,source,source['inputs'][0]['name'],depth+1)
        raise AssertionError((source['type'],source.get('title'),'dimension still driven by an automatic node'))
    targets=[]
    for g,parents in contexts:
        for n in g['nodes']:
            if n['type'] in LATENTS or (n['type']=='ImageScale' and n.get('title')=='Resize reference to render width and height'):
                for dim in ('width','height'):
                    control,name,value,factor=resolve(g,parents,n,dim)
                    assert isinstance(value,(int,float)) and value>0,(n['id'],dim,value)
                    targets.append((g,parents,n,dim,control,name,factor))
    # Change the controls, then follow the actual graph links to each render input.
    for g,parents,n,dim,control,name,factor in targets:
        expected=1280 if dim=='width' else 736
        if name=='value':control['widgets_values'][0]=expected
        else:
            names=[i['name'] for i in control['inputs'] if i.get('widget')]
            if not control.get('widgets_values') and control.get('properties',{}).get('proxyWidgets'):
                inner,index=proxy_widget(control,name);inner['widgets_values'][index]=expected
            else:control['widgets_values'][names.index(name)]=expected
            if name in control.get('widgets_values_named',{}):control['widgets_values_named'][name]=expected
        assert resolve(g,parents,n,dim)[2]==expected*factor
    return len(targets)

def fitted(width, height, image_width, image_height, **flags):
    names=dict(a=width,b=height,c=image_width,d=image_height,max=max,round=round,sqrt=math.sqrt,**flags)
    return tuple(eval(fit_expression(*sides,32),{'__builtins__':{}},names) for sides in (('c','d'),('d','c')))

# The area stays put while the image sets the proportions, so a portrait is never sliced.
assert fitted(1280,720,1920,1080)==(1280,704)
assert fitted(720,1280,1080,1920)==(704,1280)
assert fitted(1280,720,1024,1536)==(768,1184)
assert fitted(960,544,3000,3000)==(736,736)

# Every workflow that starts from a picture fits to it, and honours its off switch.
for name,expression in (('01_LTX25_Image_to_Video.json','a if e else '),('03_LTX25_First_Last_Frame.json',''),
                        ('04_LTX25_Audio_to_Video.json','a if not e else '),('06_LTX25_Two_Stage_Advanced.json','a if e else ')):
    data=json.loads((ROOT/'versions/ltx-2.5/workflows'/name).read_text())
    found=[n['widgets_values'][0] for g in data['definitions']['subgraphs'] for n in g['nodes'] if n.get('title')=='Fit Frame Width']
    assert found==[expression+fit_expression('c','d',32)],(name,found)
    if name.startswith('03_'):
        crops=[n['widgets_values'][3] for g in data['definitions']['subgraphs'] for n in g['nodes'] if n['type']=='ResizeImageMaskNode' and n['id']==213]
        assert crops==['disabled'],crops

count=0
for path in sorted(ROOT.glob('versions/*/workflows/*.json')):
    if path.name.startswith('LTX25_'):continue
    d=json.loads(path.read_text())
    before=copy.deepcopy(d)
    apply_dimensions(d,(768,448) if 'Ingredients' in path.name else None)
    assert d==before,(path.name,'dimensions were not packaged or packaging is not idempotent')
    if any(n['type'] in ('AcdevFluxStudio','AcdevIdeogramStudio') for n in d['nodes']):continue
    found=inspect(d)
    assert found or 'Audio' in path.name and not any(n['type']=='SaveVideo' for n in d['nodes']),(path.name,'no editable render dimensions')
    count+=1
print('PASS: editable width/height reach render inputs; packaging is idempotent (%d workflows).'%count)
