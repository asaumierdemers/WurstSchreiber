# WurstSchreiber is a tool for drawing segments as sausages.
# Many thanks to Just van Rossum

from fontTools.misc.bezierTools import splitCubicAtT
from fontTools.pens.basePen import BasePen
import math

from AppKit import NSColor
from mojo.extensions import getExtensionDefault, setExtensionDefault, getExtensionDefaultColor, setExtensionDefaultColor
from mojo.events import addObserver, removeObserver
from mojo.UI import UpdateCurrentGlyphView
from mojo.drawingTools import *
from vanilla import *

# constants
kappa = 4*(math.sqrt(2)-1)/3
curvecorrection = 1.25

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
        angle = math.acos((bc*bc+ab*ab-ac*ac)/(2*bc*ab)) # Law of cosines
    except ValueError: # math domain error
        return None
    except ZeroDivisionError: # prev point has same position as point
        return None
    else:
        return angle

def distance((ax, ay), (bx, by)):
    return math.sqrt((bx-ax)**2 + (by-ay)**2)

def slope((ax, ay), (bx, by)):
    return (bx-ax), (by-ay)

def normalise(a, b):
    n = math.sqrt((a*a)+(b*b))
    if n != 0:
        return (a/n, b/n)
    else:
        return (0, 0)

def interpolate((ax, ay), (bx, by), f):
    cx = ax + f * (bx - ax)
    cy = ay + f * (by - ay)
    return (cx, cy)

def offsetPoint((ax, ay), (nx, ny), radius):
    px = ax+nx*radius
    py = ay+ny*radius
    return (px, py)

def arcControlPoint((ax, ay), (nx, ny), radius):
    px = ax+nx*radius*kappa
    py = ay+ny*radius*kappa
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
    unknownAngle = 180 - knownAngle - partialAngle;
    unknownSide = ratio * math.sin(math.radians(unknownAngle)) # Law of sines
    return unknownSide


class PreviewPen(BasePen):

    def _moveTo(self, p1):
        moveTo(p1)
    def _lineTo(self, p1):
        lineTo(p1)
    def _curveToOne(self, p1, p2, p3):
        curveTo(p1, p2, p3)
    def _closePath(self):
        closepath()

class WurstPen(BasePen):

    def __init__(self, glyphSet, radius, draw):
        BasePen.__init__(self, glyphSet)

        self.radius = radius
        self.draw = draw
        self.glyph = CurrentGlyph()
        self.glyphcopy = self.glyph.copy()

        if self.draw:
            self.glyphcopy.clear()

    def _moveTo(self, pt1):
        self._prevPoint = None

    def _lineTo(self, pt1):
        radius = self.radius
        pt0 = self._getCurrentPoint()
        if self._prevPoint is None:
            self.drawWurstKnot(pt0, pt1, radius)
        margin = self.calcWurstMargin(pt0, pt1)
        self.drawLineWurst(pt0, pt1, radius, margin)
        self._prevPoint = pt0

    def _curveToOne(self, pt1, pt2, pt3):
        radius = self.radius
        pt0 = self._getCurrentPoint()
        if self._prevPoint is None:
            self.drawWurstKnot(pt0, pt1, radius)
        margin = self.calcWurstMargin(pt0, pt1)
        self.drawCurveWurst(pt0, pt1, pt2, pt3, radius, margin)
        self._prevPoint = pt2

    def _closePath(self):
        # if closed contour that finish in line, need to draw a sausage here ?
        self._prevPoint = self._getCurrentPoint()

    def _endPath(self):
        if self._prevPoint is not None:
            pt0 = self._prevPoint
            pt1 = self._getCurrentPoint()
            radius = self.radius
            self.drawWurstKnot(pt1, pt0, radius)
        self._prevPoint = self._getCurrentPoint()

    def _getPrevPoint(self):
        return self._prevPoint

    def getPath(self):
        if self.draw:
            path = self.glyphcopy.getPen()
        else:
            path = PreviewPen(None)
        return path

    def calcWurstMargin(self, pt0, pt1):
        radius = self.radius
        if self._prevPoint:
            angle = calcAngle(self._prevPoint, pt0, pt1)
            if angle and math.degrees(angle) != 180:
                margin = calcTriangleSSA(angle, radius*2, radius) - radius
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

        a = offsetPoint(p0, o1, -radius*curvecorrection)
        b = offsetPoint(p0, o2, -radius*curvecorrection)
        c = offsetPoint(p0, o3, -radius*curvecorrection)
        d = offsetPoint(p0, o4, -radius*curvecorrection)

        path = self.getPath()

        newPath()

        path.moveTo(a)
        path.lineTo(b)
        path.lineTo(c)
        path.lineTo(d)
        path.closePath()

        drawPath()

    def drawWurstCap(self, path, p, n, m, radius):
        a = offsetPoint(p, m, -radius)
        d = offsetPoint(p, n, radius*curvecorrection)
        b, c = arcControlPoints(a, (-n[0], -n[1]), d, m, -radius*curvecorrection)
        g = offsetPoint(p, m, radius)
        e, f = arcControlPoints(d, m, g, n, radius*curvecorrection)

        path.curveTo(b, c, d)
        path.curveTo(e, f, g)

    def drawWurstCurveSide(self, path, p0, p1, p2, p3, m1, m2, cdistance, radius):
        a = offsetPoint(p0, m1, radius)
        d = offsetPoint(p3, m2, -radius)

        rdistance = distance(a, d)
        rscale = rdistance/cdistance

        cp1 = interpolate(p0, p1, rscale)
        cp2 = interpolate(p3, p2, rscale)
        b = offsetPoint(cp1, m1, radius)
        c = offsetPoint(cp2, m2, -radius)

        path.curveTo(b, c, d)

    def drawWurstLineSide(self, path, p, m, radius):
        b = offsetPoint(p, m, radius)
        path.lineTo(b)

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

        path = self.getPath()

        newPath()

        start = offsetPoint(p0, m1, -radius)
            path.moveTo(start)
            self.drawWurstCap(path, p0, n1, m1, radius)
            self.drawWurstCurveSide(path, p0, p1, p2, p3, m1, m2, cdistance, radius)
            self.drawWurstCap(path, p3, n2, m2, radius)
            self.drawWurstCurveSide(path, p3, p2, p1, p0, m2, m1, cdistance, radius)
            path.closePath()

            drawPath()

    def drawLineWurst(self, p0, p1, radius, margin):
        if distance(p0, p1) < radius:
            return

        p0 = splitLineAt(p0, p1, radius+margin)
        p1 = splitLineAt(p1, p0, radius)

        dx, dy = slope(p1, p0)
        n = normalise(dx, dy)
        m = n[1], -n[0]

        path = self.getPath()

            newPath()

            start = offsetPoint(p0, m, -radius)
            path.moveTo(start)
            self.drawWurstCap(path, p0, n, m, radius)
            self.drawWurstLineSide(path, p1, m, radius)
            self.drawWurstCap(path, p1, n, m, -radius)
            path.closePath()

            drawPath()


class SliderGroup(Group):
    def __init__(self, posSize, minValue, maxValue, value, callback):
        Group.__init__(self, posSize)
        self.slider = Slider((2, 3, -55, 17), minValue=minValue, maxValue=maxValue, value=value, sizeStyle="regular", callback=self.sliderChanged)
        self.edit = EditText((-40, 0, -0, 22), text=str(value), placeholder=str(value), callback=self.editChanged)
        self.callback = callback

    def sliderChanged(self, sender):
        self.edit.set(str(int(self.slider.get())))
        self.callback(sender)

    def editChanged(self, sender):
        try:
            value = int(float(self.edit.get()))
        except ValueError:
            value = int(self.edit.getPlaceholder())
            self.edit.set(value)
        self.slider.set(value)
        self.callback(sender)


WurstSchreiberDefaultKey = "com.asaumierdemers.WurstSchreiber"

class WurstSchreiber(object):

    def __init__(self):

        self.draw = False
        self.swap = True

        self.radius = getExtensionDefault("%s.%s" %(WurstSchreiberDefaultKey, "radius"), 60)

        color = NSColor.colorWithCalibratedRed_green_blue_alpha_(1, 0, 0, .5)
        colorValue = getExtensionDefaultColor("%s.%s" %(WurstSchreiberDefaultKey, "color"), color)

        self.w = FloatingWindow((150, 170), "WurstSchreiber")
        x = 15
        y = 15
        self.w.preview = CheckBox((x, y, -x, 20), "Preview", callback=self.previewChanged, value=True)
        y+=30
        self.w.slider = SliderGroup((x, y, -x, 22), 0, 100, self.radius, callback=self.sliderChanged)
        y+=35
        self.w.color = ColorWell((x, y, -x, 40), callback=self.colorChanged, color=colorValue)
        y+=55
        self.w.button = Button((x, y, -x, 20), "Trace!", callback=self.traceButton)
        addObserver(self, "drawWurst", "drawBackground")
        self.w.bind("close", self.closing)
        self.w.open()

    def closing(self, sender):
        removeObserver(self, "drawBackground")

    def previewChanged(self, sender):
        UpdateCurrentGlyphView()

    def sliderChanged(self, sender):
        self.radius = int(sender.get())
        setExtensionDefault("%s.%s" %(WurstSchreiberDefaultKey, "radius"), self.radius)
        UpdateCurrentGlyphView()

    def colorChanged(self, sender):
        setExtensionDefaultColor("%s.%s" %(WurstSchreiberDefaultKey, "color"), sender.get())
        UpdateCurrentGlyphView()

    def getColor(self):
        color = self.w.color.get()
        return color.getRed_green_blue_alpha_(None, None, None, None)

    def traceButton(self, sender):
        if self.w.preview.get():
            self.draw = True
            UpdateCurrentGlyphView()

    def drawWurst(self, sender):
        if self.w.preview.get():
            radius = self.radius
            draw = self.draw
            r,g,b,a = self.getColor()
            fill(r,g,b,a)
            glyph = CurrentGlyph()
            pen = WurstPen(None, radius, draw)
            glyph.draw(pen)
            if self.draw:
                glyph.prepareUndo("WurstTrace")
                if self.swap:
                    glyph.getLayer("background").clear()
                    glyph.swapToLayer("background")
                glyph.appendGlyph(pen.glyphcopy)
                self.draw = False
                self.w.preview.set(False)
                glyph.performUndo()
            glyph.update()

WurstSchreiber()