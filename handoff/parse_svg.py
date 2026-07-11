import re, sys
from collections import defaultdict

NS = '{http://www.w3.org/2000/svg}'
import xml.etree.ElementTree as ET

def parse_matrix(t):
    # returns (tx, ty) assuming matrix(a b c d e f) with no rotation/scale
    m = re.match(r'matrix\(([^)]+)\)', t)
    if not m: return (0.0, 0.0)
    vals = [float(x) for x in m.group(1).split()]
    if len(vals) == 6:
        return (vals[4], vals[5])
    return (0.0, 0.0)

def parse_translate(t):
    m = re.search(r'translate\(([^)]+)\)', t)
    if not m: return (0.0, 0.0)
    vals = [float(x) for x in m.group(1).split()]
    if len(vals) == 1: return (vals[0], 0.0)
    if len(vals) >= 2: return (vals[0], vals[1])
    return (0.0, 0.0)

def rect_info(el):
    x = float(el.get('x', '0'))
    y = float(el.get('y', '0'))
    w = float(el.get('width', '0'))
    h = float(el.get('height', '0'))
    rx = el.get('rx', None)
    fill = el.get('fill', 'none')
    tr = el.get('transform', '')
    if tr:
        if 'matrix' in tr:
            tx, ty = parse_matrix(tr)
            x += tx; y += ty
        elif 'translate' in tr:
            tx, ty = parse_translate(tr)
            x += tx; y += ty
    return dict(x=round(x,1), y=round(y,1), w=round(w,1), h=round(h,1), rx=rx, fill=fill)

for fname in ['2_3.svg','6_2.svg','5_2.svg','5_126.svg']:
    print('\n' + '='*70)
    print('FILE:', fname)
    print('='*70)
    tree = ET.parse(fname)
    root = tree.getroot()
    rects = []
    for el in root.iter(NS+'rect'):
        rects.append(rect_info(el))
    # sort by y then x
    rects.sort(key=lambda r:(r['y'], r['x']))
    print(f'Total rects: {len(rects)}')
    for r in rects:
        rx = f" rx={r['rx']}" if r['rx'] else ""
        print(f"  x={r['x']:>7} y={r['y']:>7} w={r['w']:>7} h={r['h']:>7} fill={r['fill']}{rx}")
