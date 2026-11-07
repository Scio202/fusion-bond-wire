import adsk.core, adsk.fusion, traceback, math, os, time

CMD_ID = 'bondWireCmd'
_busy = False
_skip_until = 0  # ignore preview events caused by our own selection restore
PROFILES = ('Smooth curve', 'JEDEC 4-point (JESD59 simplified)', 'JEDEC 5-point (JESD59 preferred)')
JOINS = ('None', 'Face 1 body', 'Face 2 body', 'Both (merges the two bodies)')
app = adsk.core.Application.get()
ui = app.userInterface
_handlers = []
DK = 0.125  # JEDEC 4-point: flat top spans D/8
T = 0.4     # how far down the descent line the 2nd control point sits (0=at crest, 1=at landing)
N = 10  # fit points sampled along the Bezier (11 points)


def _controls(dx, dz, h1):
    """Cubic Bezier shaped like a JEDEC 4-point wire: vertical rise, short crest, straight descent
    onto the stitch. Apex is solved to sit exactly h1 above the start point (the bond pad, as in JESD59)."""
    A = h1

    def ctrl(Hc):
        return [(0, 0), (0, Hc), (dx*(DK + T*(1 - DK)), Hc + T*(dz - Hc)), (dx, dz)]

    def apex(Hc):
        return max(_bezier(*ctrl(Hc), i/100)[1] for i in range(101))

    lo, hi = A, 8*A
    for _ in range(40):
        mid = (lo + hi)/2
        lo, hi = (mid, hi) if apex(mid) < A else (lo, mid)
    return ctrl(hi)


def _polyline(dx, dz, h1, five, alpha, beta):
    """EIA/JEDEC 59 wire path, origin at the bond pad. Simplified model: alpha = 90 deg, no 4th point."""
    x2 = h1 / math.tan(alpha) if five else 0
    pts = [(0, 0), (x2, h1), (x2 + dx / 8, h1)]
    if five:
        pts.append((dx / 2, dz + dx / 2 * math.tan(beta)))
    pts.append((dx, dz))
    return pts


def _check(pts, dx, dz, h1, five):
    if five and not (pts[2][0] < pts[3][0] < dx and pts[3][1] < h1):
        raise ValueError('Angles give an invalid loop: lower alpha or beta')


def _polylen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _mid(curve):
    ev = curve.evaluator
    _, p0, p1 = ev.getParameterExtents()
    _, ln = ev.getLengthAtParameter(p0, p1)
    _, p = ev.getParameterAtLength(p0, ln / 2)
    return ev.getPointAtParameter(p)[1]


def _point(e):
    if isinstance(e, adsk.fusion.SketchPoint):
        return e.worldGeometry
    if isinstance(e, (adsk.fusion.SketchCircle, adsk.fusion.SketchArc)):
        return e.centerSketchPoint.worldGeometry      # circle/arc center
    if isinstance(e, adsk.fusion.SketchCurve):
        return _mid(e.worldGeometry)                  # line etc: midpoint
    if isinstance(e, adsk.fusion.BRepFace):
        return e.centroid                             # circle/rectangle face center
    if isinstance(e, adsk.fusion.Profile):
        return e.areaProperties().centroid            # sketch rectangle/circle center
    if isinstance(e, adsk.fusion.BRepEdge):
        g = e.geometry
        return g.center if hasattr(g, 'center') else _mid(g)
    return e.geometry  # ConstructionPoint / BRepVertex


def _body(e):
    return e.body if isinstance(e, (adsk.fusion.BRepFace, adsk.fusion.BRepEdge, adsk.fusion.BRepVertex)) else None


def _combine(root, target, tool, op, keep):
    tools = adsk.core.ObjectCollection.create()
    tools.add(tool)
    ci = root.features.combineFeatures.createInput(target, tools)
    ci.operation = op
    ci.isKeepToolBodies = keep
    root.features.combineFeatures.add(ci)


def _extend(tx, ty, r, dia):
    """Length to push a wire end along its tangent so the whole end disc sits inside the pad body."""
    s = abs(ty) / math.hypot(tx, ty)       # vertical fraction of the tangent
    return r * math.sqrt(1 - s*s) / max(s, 0.05) + dia


MATS = ('Gold', 'Copper', 'Aluminum', 'Silver')


def _appearance(des, metal):
    lib = app.materialLibraries.itemByName('Fusion Appearance Library').appearances
    for finish in ('Polished', 'Satin'):          # polished preferred, satin fallback
        name = '%s - %s' % (metal, finish)
        src = lib.itemByName(name)
        if src:
            return des.appearances.itemByName(name) or des.appearances.addByCopy(src, name)


def _bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u**3*a + 3*u*u*t*b + 3*u*t*t*c + t**3*d
                 for a, b, c, d in zip(p0, p1, p2, p3))


def _light_ui():
    """True when Fusion's UI is light (picks the dark-text picture). 'Match OS' reads the Windows setting."""
    T = adsk.core.UserInterfaceThemes
    t = app.preferences.generalPreferences.userInterfaceTheme
    if t == T.DeviceUserInterfaceTheme:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
            return winreg.QueryValueEx(k, 'AppsUseLightTheme')[0] == 1
        except Exception:
            return False
    return t in (T.LightGrayUserInterfaceTheme, T.ClassicUserInterfaceTheme)


def _length(P):
    pts = [_bezier(*P, i / 60) for i in range(61)]
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(60))


def build(inputs, e0, e1):
    """Create the wire (sketch + pipe + trim + optional joins). Returns wire length in cm."""
    a, b = _point(e0), _point(e1)
    dia = inputs.itemById('dia').value   # cm (Fusion internal units)
    h = inputs.itemById('h').value
    profile = inputs.itemById('profile').selectedItem.name
    smooth = profile.startswith('Smooth')
    five = profile.startswith('JEDEC 5')
    alpha = inputs.itemById('alpha').value    # radians
    beta = inputs.itemById('beta').value

    # vertical plane through both points: u = horizontal dir toward b, v = world Z
    dx = math.hypot(b.x - a.x, b.y - a.y)
    dz = b.z - a.z
    u = adsk.core.Vector3D.create(b.x - a.x, b.y - a.y, 0)
    if dx < 1e-9:
        u = adsk.core.Vector3D.create(1, 0, 0)
    u.normalize()
    # validate before touching the design so a bad input leaves nothing behind
    pl = None if smooth else _polyline(dx, dz, h, five, alpha, beta)
    if h <= max(0, dz):
        raise ValueError('Loop height h1 must be above both points (h1 > dz)')
    if pl:
        _check(pl, dx, dz, h, five)

    root = app.activeProduct.rootComponent
    # 3D splines on a plain XY sketch (needs "Allow 3D sketching" pref; points are world coords)
    fp = adsk.fusion.FusionProductPreferences.cast(app.preferences.productPreferences.itemByName('Design'))
    was = fp.is3DSketchingAllowed       # restored below: it's the user's setting, not ours
    fp.is3DSketchingAllowed = True
    try:
        sk = root.sketches.add(root.xYConstructionPlane)
        sk.name = 'BondWire'

        b0, b1 = _body(e0), _body(e1)
        land = e1 if isinstance(e1, adsk.fusion.BRepFace) and e1.geometry.objectType == adsk.core.Plane.classType() else None
        metal = inputs.itemById('mat').selectedItem.name
        W = lambda p: adsk.core.Point3D.create(a.x + u.x*p[0], a.y + u.y*p[0], a.z + p[1])
        if smooth:
            P = _controls(dx, dz, h)
            length = _length(P)
            pts = adsk.core.ObjectCollection.create()
            for i in range(N + 1):
                pts.add(W(_bezier(*P, i / N)))
            first = sk.sketchCurves.sketchFittedSplines.add(pts)
            # landing on a planar face: continue straight along the spline's end tangent into the pad, then split at its plane
            # (Fusion can't sweep a pipe along a control-point spline, so this is a fitted one)
            if land:
                ev = first.geometry.evaluator
                t = ev.getTangent(ev.getParameterExtents()[2])[1]
                t.normalize()
                L1 = _extend(math.hypot(t.x, t.y), t.z, dia / 2, dia)
                e = first.endSketchPoint.geometry
                sk.sketchCurves.sketchLines.addByTwoPoints(
                    first.endSketchPoint, adsk.core.Point3D.create(e.x + t.x*L1, e.y + t.y*L1, e.z + t.z*L1))
        else:
            length = _polylen(pl)
            run_pts = list(pl)
            if land:   # extend the last (straight) segment into the pad; the plane split then cuts it flush
                tx, tz = pl[-1][0] - pl[-2][0], pl[-1][1] - pl[-2][1]
                n = math.hypot(tx, tz)
                L1 = _extend(tx, tz, dia / 2, dia)
                run_pts[-1] = (pl[-1][0] + tx / n * L1, pl[-1][1] + tz / n * L1)
            lines = []
            for i in range(len(run_pts) - 1):
                start = lines[-1].endSketchPoint if lines else W(run_pts[0])
                lines.append(sk.sketchCurves.sketchLines.addByTwoPoints(start, W(run_pts[i + 1])))
            first = lines[0]
    finally:
        fp.is3DSketchingAllowed = was

    path = root.features.createPath(first, True)
    pi = root.features.pipeFeatures.createInput(path, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    pi.sectionSize = adsk.core.ValueInput.createByReal(dia)
    wire = root.features.pipeFeatures.add(pi).bodies.item(0)

    ap = _appearance(app.activeProduct, metal)
    if ap:
        wire.appearance = ap
    wire.name = 'BondWire'

    if land:  # split at the pad's plane; the smaller piece is the overshoot stub
        sf = root.features.splitBodyFeatures.add(
            root.features.splitBodyFeatures.createInput(wire, land, False))   # the face itself, not its infinite plane: a higher pad would also cut the neck
        pieces = sorted(sf.bodies, key=lambda b: b.volume)
        root.features.removeFeatures.add(pieces[0])
        wire = pieces[-1]
        # the straight overshoot leaves a separate cylinder face; delete it so the neighbours heal into one face
        for f in (wire.faces if smooth else []):
            if f.geometry.objectType == adsk.core.Cylinder.classType():
                root.features.deleteFaceFeatures.add(f)
                break
        wire.name = 'BondWire'
        if ap:
            wire.appearance = ap

    mode = inputs.itemById('join').selectedItem.name
    want = {'Face 1 body': [b0], 'Face 2 body': [b1]}.get(mode, [b0, b1] if mode.startswith('Both') else [])
    want = [x for x in want if x]
    if want:
        J = adsk.fusion.FeatureOperations.JoinFeatureOperation
        _combine(root, want[0], wire, J, False)
        # "Both": the wire already bridges them, so fusing the second body into the first is clean
        if len(want) > 1 and want[1].entityToken != want[0].entityToken:
            _combine(root, want[0], want[1], J, False)
    return length


NEEDS_PARAMETRIC = 'Needs a parametric design: turn on Capture Design History.'


def _parametric():
    d = adsk.fusion.Design.cast(app.activeProduct)
    return bool(d) and d.designType == adsk.fusion.DesignTypes.ParametricDesignType


def _run(args, preview):
    global _busy, _skip_until
    if _busy or time.time() < _skip_until:
        return
    ins = args.command.commandInputs
    if not _parametric():
        if preview:
            ins.itemById('status').text = NEEDS_PARAMETRIC
        else:
            ui.messageBox(NEEDS_PARAMETRIC)
        return
    sel = ins.itemById('pts')
    if sel.selectionCount != 2 or (preview and not ins.itemById('live').value):
        return
    e0, e1 = sel.selection(0).entity, sel.selection(1).entity  # read first: creating a sketch clears the selection
    _busy = True
    try:
        length = build(ins, e0, e1)
        ins.itemById('status').text = 'Wire length %.3f mm' % (length * 10)
    except:
        if preview:
            ins.itemById('status').text = traceback.format_exc().strip().splitlines()[-1][:120]
        else:
            ui.messageBox(traceback.format_exc())
    finally:
        if preview and sel.selectionCount < 2:   # building geometry wipes the picks; put them back
            _skip_until = time.time() + 0.5
            for e in (e0, e1):
                sel.addSelection(e)
        _busy = False


class Exec(adsk.core.CommandEventHandler):
    def notify(self, args):
        _run(args, False)


class Preview(adsk.core.CommandEventHandler):
    def notify(self, args):
        _run(args, True)


class Changed(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        if args.input.id == 'profile':      # alpha / beta only exist in the 5-point model
            five = args.input.selectedItem.name.startswith('JEDEC 5')
            for k in ('alpha', 'beta'):
                args.inputs.itemById(k).isVisible = five


class Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        cmd = args.command
        i = cmd.commandInputs
        cmd.setDialogInitialSize(340, 560)   # default opens too narrow for the picture
        light = _light_ui()
        i.addImageCommandInput('img', '', os.path.join(os.path.dirname(os.path.realpath(__file__)), 'profile_light.png' if light else 'profile_dark.png'))
        s = i.addSelectionInput('pts', 'Points', 'Select start (die) and end point')
        s.setSelectionLimits(2, 2)
        for f in ('Vertices', 'ConstructionPoints', 'SketchPoints', 'Edges', 'Faces', 'SketchCurves', 'Profiles'):
            s.addSelectionFilter(f)
        V = adsk.core.ValueInput.createByString
        i.addValueInput('dia', 'Wire diameter', 'mm', V('0.025 mm'))
        i.addValueInput('h', 'Loop height (h1)', 'mm', V('0.2 mm'))
        pr = i.addDropDownCommandInput('profile', 'Profile', adsk.core.DropDownStyles.TextListDropDownStyle)
        for k in PROFILES:
            pr.listItems.add(k, k == PROFILES[0])
        i.addAngleValueCommandInput('alpha', 'Pad angle (alpha)', V('90 deg')).isVisible = False
        i.addAngleValueCommandInput('beta', 'Lead angle (beta)', V('15 deg')).isVisible = False
        m = i.addDropDownCommandInput('mat', 'Material', adsk.core.DropDownStyles.TextListDropDownStyle)
        for k in MATS:
            m.listItems.add(k, k == 'Gold')
        j = i.addDropDownCommandInput('join', 'Join wire to', adsk.core.DropDownStyles.TextListDropDownStyle)
        for k in JOINS:
            j.listItems.add(k, k == 'None')
        i.addBoolValueInput('live', 'Live preview', True, '', True)
        i.addTextBoxCommandInput('status', '', 'Select two points' if _parametric() else NEEDS_PARAMETRIC, 2, True)
        for hnd, ev in ((Exec(), cmd.execute), (Preview(), cmd.executePreview), (Changed(), cmd.inputChanged)):
            ev.add(hnd); _handlers.append(hnd)


def run(context):
    try:
        d = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, 'Bond Wire', 'Create a bond wire between two points',
            os.path.join(os.path.dirname(os.path.realpath(__file__)), 'bw_icons'))
        h = Created(); d.commandCreated.add(h); _handlers.append(h)
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.addCommand(d)
    except:
        ui.messageBox(traceback.format_exc())


def stop(context):
    try:
        c = ui.allToolbarPanels.itemById('SolidCreatePanel').controls.itemById(CMD_ID)
        if c: c.deleteMe()
        d = ui.commandDefinitions.itemById(CMD_ID)
        if d: d.deleteMe()
    except:
        pass
