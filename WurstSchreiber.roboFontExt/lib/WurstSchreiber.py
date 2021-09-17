# WurstSchreiber is a tool for drawing segments as sausages.
# Many thanks to Just van Rossum

from fontTools.misc.bezierTools import splitCubicAtT
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
import math
import vanilla

from mojo.roboFont import CurrentGlyph
from mojo.extensions import getExtensionDefault, setExtensionDefault
from mojo.extensions import getExtensionDefaultColor, setExtensionDefaultColor
from mojo.extensions import rgbaToNSColor, NSColorToRgba

from mojo.subscriber import WindowController, Subscriber, registerGlyphEditorSubscriber, registerSubscriberEvent, roboFontSubscriberEventRegistry
from mojo.events import postEvent

# constants
KAPPA = 4*(math.sqrt(2)-1)/3
CURVE_CORRECTION = 1.25


class Vector(object):

    def __init__(self, v):
        self.v = v

    def __add__(self, other):
        x, y = self.v
        x2, y2 = other
        return Vector((x+x2, y+y2))

    def __sub__(self, other):
        x, y = self.v
        x2, y2 = other
        return Vector((x-x2, y-y2))

    def __mul__(self, m):
        x, y = self.v
        return Vector((x*m, y*m))

    def __div__(self, d):
        x, y = self.v
        return Vector((x/d, y/d))

    def __iter__(self):
        return iter(self.v)


def calcCubicParameters(pt1, pt2, pt3, pt4):
    pt1 = Vector(pt1)
    pt2 = Vector(pt2)
    pt3 = Vector(pt3)
    pt4 = Vector(pt4)
    d = pt1
    c = (pt2 - d) * 3.0
    b = (pt3 - pt2) * 3.0 - c
    a = pt4 - d - c - b
    return a, b, c, d


def calcAngle(a, b, c):
    ab = distance(a, b)
    bc = distance(b, c)
    ac = distance(a, c)
    try:
        angle = math.acos((bc*bc+ab*ab-ac*ac)/(2*bc*ab))  # Law of cosines
    except ValueError:  # math domain error
        return None
    except ZeroDivisionError:  # prev point has same position as point
        return None
    else:
        return angle


def distance(pt_a, pt_b):
    ax, ay = pt_a
    bx, by = pt_b
    return math.sqrt((bx-ax)**2 + (by-ay)**2)


def slope(pt_a, pt_b):
    ax, ay = pt_a
    bx, by = pt_b
    return (bx-ax), (by-ay)


def normalise(a, b):
    n = math.sqrt((a*a)+(b*b))
    if n != 0:
        return (a/n, b/n)
    else:
        return (0, 0)


def interpolate(pt_a, pt_b, f):
    ax, ay = pt_a
    bx, by = pt_b
    cx = ax + f * (bx - ax)
    cy = ay + f * (by - ay)
    return (cx, cy)


def offsetPoint(pt_a, pt_n, radius):
    ax, ay = pt_a
    nx, ny = pt_n
    px = ax+nx*radius
    py = ay+ny*radius
    return (px, py)


def arcControlPoint(pt_a, pt_n, radius):
    ax, ay = pt_a
    nx, ny = pt_n
    px = ax+nx*radius*KAPPA
    py = ay+ny*radius*KAPPA
    return (px, py)


def arcControlPoints(a, an, b, bn, radius):
    p1 = arcControlPoint(a, an, radius)
    p2 = arcControlPoint(b, bn, radius)
    return p1, p2


def splitCubicAtLength(p0, p1, p2, p3, length):
    a, b, c, d = calcCubicParameters(p0, p1, p2, p3)
    a1 = a * 3.0
    b1 = b * 2.0
    c1 = c
    t = 0
    dx, dy = a1 * t ** 2 + b1 * t + c1
    velocity = math.sqrt(dx ** 2 + dy ** 2)
    s = length / velocity
    return s


def splitLineAt(p0, p1, length):
    ldistance = distance(p0, p1)
    x1, y1 = p0
    x2, y2 = p1
    x = x1+(length/ldistance)*(x2-x1)
    y = y1+(length/ldistance)*(y2-y1)
    return x, y


def calcTriangleSSA(angle, side1, side2):
    knownAngle = math.degrees(angle)
    knownSide = side1
    partialSide = side2
    ratio = knownSide / math.sin(math.radians(knownAngle))
    if ratio == 0:
        return 0
    temp = partialSide / ratio
    partialAngle = math.degrees(math.asin(temp))
    unknownAngle = 180 - knownAngle - partialAngle
    unknownSide = ratio * math.sin(math.radians(unknownAngle))   # Law of sines
    return unknownSide


class WurstPen(BasePen):

    def __init__(self, glyphSet, pen, radius):
        super().__init__(glyphSet)
        self.radius = radius
        self.pen = pen

    def _moveTo(self, pt1):
        self._firstPoint = pt1
        self._prevPoint = None

    def _lineTo(self, pt1):
        pt0 = self._getCurrentPoint()
        if self._prevPoint is None:
            self.drawWurstKnot(pt0, pt1, self.radius)
        margin = self.calcWurstMargin(pt0, pt1)
        self.drawLineWurst(pt0, pt1, self.radius, margin)
        self._prevPoint = pt0

    def _curveToOne(self, pt1, pt2, pt3):
        pt0 = self._getCurrentPoint()
        if self._prevPoint is None:
            self.drawWurstKnot(pt0, pt1, self.radius)
        margin = self.calcWurstMargin(pt0, pt1)
        self.drawCurveWurst(pt0, pt1, pt2, pt3, self.radius, margin)
        self._prevPoint = pt2

    def _closePath(self):
        if self._firstPoint != self._getCurrentPoint():
            self.lineTo(self._firstPoint)

    def _endPath(self):
        if self._prevPoint is not None:
            pt0 = self._prevPoint
            pt1 = self._getCurrentPoint()
            self.drawWurstKnot(pt1, pt0, self.radius)
        self._prevPoint = self._getCurrentPoint()

    def calcWurstMargin(self, pt0, pt1):
        if self._prevPoint:
            angle = calcAngle(self._prevPoint, pt0, pt1)
            if angle and math.degrees(angle) != 180:
                margin = calcTriangleSSA(angle, self.radius * 2, self.radius) - self.radius
            else:
                margin = 0
        else:
            margin = 0
        return margin

    def drawWurstKnot(self, p0, p1, radius):
        dx, dy = slope(p0, p1)
        n = normalise(dx, dy)
        m = n[1], -n[0]

        o1 = -m[0]*.1, -m[1]*.1
        o2 = n[0]*.5-m[0]*.25, n[1]*.5-m[1]*.25
        o3 = n[0]*.5+m[0]*.25, n[1]*.5+m[1]*.25
        o4 = m[0]*.1, m[1]*.1

        a = offsetPoint(p0, o1, -radius*CURVE_CORRECTION)
        b = offsetPoint(p0, o2, -radius*CURVE_CORRECTION)
        c = offsetPoint(p0, o3, -radius*CURVE_CORRECTION)
        d = offsetPoint(p0, o4, -radius*CURVE_CORRECTION)

        self.pen.moveTo(a)
        self.pen.lineTo(b)
        self.pen.lineTo(c)
        self.pen.lineTo(d)
        self.pen.closePath()

    def drawWurstCap(self, p, n, m, radius):
        a = offsetPoint(p, m, -radius)
        d = offsetPoint(p, n, radius*CURVE_CORRECTION)
        b, c = arcControlPoints(a, (-n[0], -n[1]), d, m, -radius*CURVE_CORRECTION)
        g = offsetPoint(p, m, radius)
        e, f = arcControlPoints(d, m, g, n, radius*CURVE_CORRECTION)

        self.pen.curveTo(b, c, d)
        self.pen.curveTo(e, f, g)

    def drawWurstCurveSide(self, p0, p1, p2, p3, m1, m2, cdistance, radius):
        a = offsetPoint(p0, m1, radius)
        d = offsetPoint(p3, m2, -radius)

        rdistance = distance(a, d)
        rscale = rdistance/cdistance

        cp1 = interpolate(p0, p1, rscale)
        cp2 = interpolate(p3, p2, rscale)
        b = offsetPoint(cp1, m1, radius)
        c = offsetPoint(cp2, m2, -radius)

        self.pen.curveTo(b, c, d)

    def drawWurstLineSide(self, p, m, radius):
        b = offsetPoint(p, m, radius)
        self.pen.lineTo(b)

    def drawCurveWurst(self, p0, p1, p2, p3, radius, margin):
        if distance(p0, p3) < radius:
            return
        if p0 == p1 or p2 == p3:
            return

        s1 = splitCubicAtLength(p0, p1, p2, p3, radius+margin)
        s2 = 1-splitCubicAtLength(p3, p2, p1, p0, radius)

        curves = splitCubicAtT(p0, p1, p2, p3, s1, s2)
        p0, p1, p2, p3 = curves[1]

        dx1, dy1 = slope(p1, p0)
        dx2, dy2 = slope(p2, p3)
        n1 = normalise(dx1, dy1)
        n2 = normalise(dx2, dy2)
        m1 = n1[1], -n1[0]
        m2 = n2[1], -n2[0]

        cdistance = distance(p0, p3)

        start = offsetPoint(p0, m1, -radius)
        self.pen.moveTo(start)
        self.drawWurstCap(p0, n1, m1, radius)
        self.drawWurstCurveSide(p0, p1, p2, p3, m1, m2, cdistance, radius)
        self.drawWurstCap(p3, n2, m2, radius)
        self.drawWurstCurveSide(p3, p2, p1, p0, m2, m1, cdistance, radius)
        self.pen.closePath()

    def drawLineWurst(self, p0, p1, radius, margin):
        if distance(p0, p1) < radius:
            return

        p0 = splitLineAt(p0, p1, radius+margin)
        p1 = splitLineAt(p1, p0, radius)

        dx, dy = slope(p1, p0)
        n = normalise(dx, dy)
        m = n[1], -n[0]

        start = offsetPoint(p0, m, -radius)
        self.pen.moveTo(start)
        self.drawWurstCap(p0, n, m, radius)
        self.drawWurstLineSide(p1, m, radius)
        self.drawWurstCap(p1, n, m, -radius)
        self.pen.closePath()


class MerzWurstPen(BasePen):

    def __init__(self, merzLayer, color):
        BasePen.__init__(self, None)
        self.merzLayer = merzLayer
        self.color = color

    def _moveTo(self, pt):
        pathLayer = self.merzLayer.appendPathSublayer()
        pathLayer.setFillColor(self.color)
        self.path = pathLayer.getPen()

        self.path.moveTo(pt)

    def _lineTo(self, pt):
        self.path.lineTo(pt)

    def _curveToOne(self, pt1, pt2, pt3):
        self.path.curveTo(pt1, pt2, pt3)

    def closePath(self):
        self.path.closePath()

    def endPath(self):
        self.path.endPath()


WurstSchreiberDefaultKey = "com.asaumierdemers.WurstSchreiber"

def drawWurst(glyph, outPen, radius):
    pen = WurstPen(glyph.layer, outPen, radius)
    glyph.draw(pen)


class WurstDefaults:

    def wurstFromDefaults(self):
        self.radius = getExtensionDefault(f"{WurstSchreiberDefaultKey}.radius", 60)
        self.color = getExtensionDefaultColor(f"{WurstSchreiberDefaultKey}.color", rgbaToNSColor((1, 0, 0, .5)))
        self.visible = getExtensionDefault(f"{WurstSchreiberDefaultKey}.visible", True)


class WurstSchreiber(Subscriber, WurstDefaults):

    debug = True

    def build(self):
        self.wurstFromDefaults()

        glyphEditor = self.getGlyphEditor()
        self.wurstLayer = glyphEditor.extensionContainer(
            identifier=f'{WurstSchreiberDefaultKey}.background',
            location='background',
            clear=True
        )

    def destroy(self):
        self.wurstLayer.clearSublayers()

    def wurstSchreiverUpdateGlyphEditor(self, info):
        self.wurstFromDefaults()
        self.wurstLayer.setVisible(self.visible)
        self.drawWurst()

    def wurstSchreiverRemoveWurst(self, info):
        self.terminate()

    def glyphEditorDidSetGlyph(self, info):
        self.drawWurst()

    glyphEditorGlyphDidChangeDelay = 0
    def glyphEditorGlyphDidChange(self, info):
        self.drawWurst()

    def drawWurst(self):
        if self.visible:
            glyph = self.getGlyphEditor().getGlyph()
            if glyph is None:
                return
            self.wurstLayer.clearSublayers()

            pen = MerzWurstPen(
                merzLayer=self.wurstLayer,
                color= NSColorToRgba(self.color),
            )

            drawWurst(glyph, pen, self.radius)


class SliderGroup(vanilla.Group):

    def __init__(self, posSize, minValue, maxValue, value, callback):
        super().__init__(posSize)
        self.slider = vanilla.Slider(
            (2, 3, -55, 17),
            minValue=minValue,
            maxValue=maxValue,
            value=value,
            sizeStyle="regular",
            callback=self.sliderChanged
        )
        self.edit = vanilla.EditText(
            (-40, 0, -0, 22),
            text=str(value),
            placeholder=str(value),
            callback=self.editChanged
        )
        self.callback = callback

    def sliderChanged(self, sender):
        self.edit.set(str(int(self.slider.get())))
        self.callback(sender)

    def get(self):
        return self.slider.get()

    def editChanged(self, sender):
        try:
            value = int(float(self.edit.get()))
        except ValueError:
            value = int(self.edit.getPlaceholder())
            self.edit.set(value)
        self.slider.set(value)
        self.callback(sender)


class WurstSchreiberController(WindowController, WurstDefaults):

    debug = True

    def build(self):
        self.wurstFromDefaults()

        self.w = vanilla.FloatingWindow((150, 170), "WurstSchreiber")
        x = 15
        y = 15
        self.w.preview = vanilla.CheckBox(
            (x, y, -x, 20),
            "Preview",
            callback=self.postChanged,
            value=self.visible
        )
        y += 30
        self.w.radiusSlider = SliderGroup(
            (x, y, -x, 22),
            minValue=0,
            maxValue=100,
            value=self.radius,
            callback=self.postChanged
        )
        y += 35
        self.w.color = vanilla.ColorWell(
            (x, y, -x, 40),
            color=self.color,
            callback=self.postChanged
        )
        y += 55
        self.w.button = vanilla.Button(
            (x, y, -x, 20),
            "Trace!",
            callback=self.traceButton
        )
        self.w.open()

    def getOptions(self):
        return dict(
            visible=self.w.preview.get(),
            radius=self.w.radiusSlider.get(),
            color=self.w.color.get()
        )

    def postChanged(self, sender):
        options = self.getOptions()
        setExtensionDefaultColor(f"{WurstSchreiberDefaultKey}.color", options["color"])
        setExtensionDefault(f"{WurstSchreiberDefaultKey}.radius", options["radius"])
        setExtensionDefault(f"{WurstSchreiberDefaultKey}.visible", options["visible"])
        postEvent(f"{WurstSchreiberDefaultKey}.updateGlyphEditor")

    def traceButton(self, sender):
        glyph = CurrentGlyph()
        options = self.getOptions()
        pen = RecordingPen()

        drawWurst(glyph, pen, options["radius"])

        background = glyph.getLayer("background")

        with background.undo("WurstTrace"):
            background.clear()
            pen.replay(background.getPen())
            background.changed()

    def windowWillClose(self, window):
        postEvent(f"{WurstSchreiberDefaultKey}.removeWurst")


if f"{WurstSchreiberDefaultKey}.updateGlyphEditor" not in roboFontSubscriberEventRegistry:
    registerSubscriberEvent(
        subscriberEventName=f"{WurstSchreiberDefaultKey}.updateGlyphEditor",
        methodName="wurstSchreiverUpdateGlyphEditor",
        lowLevelEventNames=[f"{WurstSchreiberDefaultKey}.updateGlyphEditor"],
        dispatcher="roboFont",
        delay=0.02,
    )

    registerSubscriberEvent(
        subscriberEventName=f"{WurstSchreiberDefaultKey}.removeWurst",
        methodName="wurstSchreiverRemoveWurst",
        lowLevelEventNames=[f"{WurstSchreiberDefaultKey}.removeWurst"],
        dispatcher="roboFont",
        delay=0,
    )


if __name__ == '__main__':
    OpenWindow(WurstSchreiberController)
    registerGlyphEditorSubscriber(WurstSchreiber)
