import re
import xml.dom.minidom as xml
import numpy as np
import pyqtgraph as pg
from pyqtgraph import functions as fn
from pyqtgraph.Qt import QtGui

def apply_pyqtgraph_patches():
    """
    Applies monkeypatches to pyqtgraph to fix known bugs.
    """
    try:
        import pyqtgraph.exporters.SVGExporter as svg_module
        # In some versions, 'SVGExporter' might be the class, not the module
        # due to 'from .SVGExporter import *' in exporters/__init__.py
        
        import sys
        if 'pyqtgraph.exporters.SVGExporter' in sys.modules:
            mod = sys.modules['pyqtgraph.exporters.SVGExporter']
            if hasattr(mod, 'correctCoordinates'):
                target_mod = mod
            else:
                # Try to find where correctCoordinates is
                import pyqtgraph.exporters as exporters
                if hasattr(exporters, 'correctCoordinates'):
                    target_mod = exporters
                else:
                    return
        else:
            return

        def patched_correctCoordinates(node, defs, item, options):
            # correct the defs in the linearGradient
            for d in defs:
                if d.tagName == "linearGradient":
                    d.removeAttribute("gradientUnits")
                    for coord in ("x1", "x2", "y1", "y2"):
                        try:
                            if coord.startswith("x"):
                                denominator = item.boundingRect().width()
                            else:
                                denominator = item.boundingRect().height()
                            if denominator == 0: denominator = 1
                            percentage = round(float(d.getAttribute(coord)) * 100 / denominator)
                            d.setAttribute(coord, f"{percentage}%")
                        except Exception:
                            continue
                    for child in filter(lambda e: isinstance(e, xml.Element) and e.tagName == "stop", d.childNodes):
                        offset = child.getAttribute("offset")
                        try:
                            child.setAttribute("offset", f"{round(float(offset) * 100)}%")
                        except ValueError:
                            continue

            groups = node.getElementsByTagName('g')
            groups2 = []
            for grp in groups:
                subGroups = [grp.cloneNode(deep=False)]
                textGroup = None
                for ch in grp.childNodes[:]:
                    if isinstance(ch, xml.Element):
                        if textGroup is None:
                            textGroup = ch.tagName == 'text'
                        if ch.tagName == 'text':
                            if textGroup is False:
                                subGroups.append(grp.cloneNode(deep=False))
                                textGroup = True
                        else:
                            if textGroup is True:
                                subGroups.append(grp.cloneNode(deep=False))
                                textGroup = False
                    subGroups[-1].appendChild(ch)
                groups2.extend(subGroups)
                for sg in subGroups:
                    node.insertBefore(sg, grp)
                node.removeChild(grp)
            groups = groups2

            for grp in groups:
                matrix = grp.getAttribute('transform')
                match = re.match(r'matrix\((.*)\)', matrix)
                if match is None:
                    vals = [1,0,0,1,0,0]
                else:
                    try:
                        vals = [float(a) for a in match.groups()[0].split(',')]
                    except Exception:
                        vals = [1,0,0,1,0,0]
                tr = np.array([[vals[0], vals[2], vals[4]], [vals[1], vals[3], vals[5]]])

                for ch in grp.childNodes:
                    if not isinstance(ch, xml.Element):
                        continue
                    if ch.tagName == 'polyline':
                        attr = ch.getAttribute('points').strip()
                        if not attr: continue
                        try:
                            coords = np.array([[float(a) for a in c.split(',')] for c in attr.split(' ') if ',' in c])
                            if len(coords) > 0:
                                coords = fn.transformCoordinates(tr, coords, transpose=True)
                                ch.setAttribute('points', ' '.join([','.join([str(a) for a in c]) for c in coords]))
                        except Exception:
                            continue
                    elif ch.tagName == 'path':
                        newCoords = ''
                        oldCoords = ch.getAttribute('d').strip()
                        if oldCoords == '':
                            continue
                        
                        for c in oldCoords.split(' '):
                            if not c: continue
                            if ',' not in c:
                                newCoords += c + ' '
                                continue
                            
                            try:
                                if c[0].isalpha():
                                    t = c[0]
                                    remainder = c[1:]
                                else:
                                    t = ''
                                    remainder = c
                                    
                                if ',' in remainder:
                                    parts = remainder.split(',')
                                    if len(parts) == 2:
                                        x = float(parts[0])
                                        y = float(parts[1])
                                        nc = fn.transformCoordinates(tr, np.array([[x, y]]), transpose=True)
                                        newCoords += t + str(nc[0,0]) + ',' + str(nc[0,1]) + ' '
                                    else:
                                        newCoords += c + ' '
                                else:
                                    newCoords += c + ' '
                            except Exception:
                                newCoords += c + ' '
                        
                        if newCoords:
                            newCoords = newCoords.strip()
                            if newCoords[0] != 'M' and 'M' in newCoords:
                                idx = newCoords.find('M')
                                newCoords = newCoords[idx:]
                            elif newCoords[0] != 'M':
                                newCoords = 'M' + newCoords[1:]
                            
                            ch.setAttribute('d', newCoords)
                    elif ch.tagName == 'text':
                        families = ch.getAttribute('font-family').split(',')
                        if len(families) == 1:
                            font = QtGui.QFont(families[0].strip('" '))
                            if font.styleHint() == font.StyleHint.SansSerif:
                                families.append('sans-serif')
                            elif font.styleHint() == font.StyleHint.Serif:
                                families.append('serif')
                            elif font.styleHint() == font.StyleHint.Monospace:
                                families.append('monospace')
                            ch.setAttribute('font-family', ', '.join(families))

        # Replace the original function in the target module
        target_mod.correctCoordinates = patched_correctCoordinates
        # print(f"Applied pyqtgraph SVGExporter monkeypatch to {target_mod.__name__}")
    except Exception as e:
        # print(f"Failed to apply pyqtgraph patches: {e}")
        pass
