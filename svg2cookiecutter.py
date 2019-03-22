import sys
import svgpath.parser as parser

PRELIM = """// OpenSCAD file automatically generated by svg2cookiercutter.py
// parameters tunable by user
wallHeight = 12;
minWallThickness = 2;
maxWallThickness = 3;
minInsideWallThickness = 1;
maxInsideWallThickness = 3;

wallFlareWidth = 5;
wallFlareThickness = 3;
insideWallFlareWidth = 5;
insideWallFlareThickness = 3;

featureHeight = 8;
minFeatureThickness = 1;
maxFeatureThickness = 3;

connectorThickness = 3;
cuttingTaperHeight = 2.5;
cuttingEdgeThickness = 1.25;
demouldingPlateHeight = 0; // default off
demouldingPlateSlack = 1.5;

// sizing
function featureThickness(t)    = min(maxFeatureThickness,   max(t,minFeatureThickness)) ;
function wallThickness(t)       = min(maxWallThickness,      max(t,minWallThickness)) ;
function insideWallThickness(t) = min(maxInsideWallThickness,max(t,minInsideWallThickness)) ;

size = $OVERALL_SIZE$;
scale = size/$OVERALL_SIZE$;

// helper modules: subshapes
module ribbon(points, thickness=1) {
    union() {
        for (i=[1:len(points)-1]) {
            hull() {
                translate(points[i-1]) circle(d=thickness, $fn=8);
                translate(points[i]) circle(d=thickness, $fn=8);
            }
        }
    }
}


module wall(points,height,thickness) {
    module profile() {
        if (height>=cuttingTaperHeight && cuttingTaperHeight>0 && cuttingEdgeThickness<thickness) {
            cylinder(h=height-cuttingTaperHeight+0.001,d=thickness,$fn=8);
            translate([0,0,height-cuttingTaperHeight]) cylinder(h=cuttingTaperHeight,d1=thickness,d2=cuttingEdgeThickness);
        }
        else {
            cylinder(h=height,$fn=8);
        }
    }
    for (i=[1:len(points)-1]) {
        hull() {
            translate(points[i-1]) profile();
            translate(points[i])   profile();
        }
    }
}


module outerFlare(path) {
  difference() {
    render(convexity=10) linear_extrude(height=wallFlareThickness) ribbon(path,thickness=wallFlareWidth);
    translate([0,0,-0.01]) linear_extrude(height=wallFlareThickness+0.02) polygon(points=path);
  }
}

module innerFlare(path) {
  intersection() {
    render(convexity=10) linear_extrude(height=insideWallFlareThickness) ribbon(path,thickness=insideWallFlareWidth);
    translate([0,0,-0.01]) linear_extrude(height=insideWallFlareThickness+0.02) polygon(points=path);
  }
}

module fill(path,height) {
  render(convexity=10) linear_extrude(height=height) polygon(points=path);
}

"""

def isRed(rgb):
    return rgb is not None and rgb[0] >= 0.4 and rgb[1]+rgb[2] < rgb[0] * 0.25

def isGreen(rgb):
    return rgb is not None and rgb[1] >= 0.4 and rgb[0]+rgb[2] < rgb[1] * 0.25

def isBlack(rgb):
    return rgb is not None and rgb[0]+rgb[1]+rgb[2]<0.2

class Line(object):
    def __init__(self, pathName, points, fill, stroke, strokeWidth):
        self.pathName = pathName
        self.points = points
        self.fill = fill
        self.stroke = stroke
        self.strokeWidth = strokeWidth

    def pathCode(self):
        return self.pathName + ' = scale * [' + ','.join(('[%.3f,%.3f]'%tuple(p) for p in self.points)) + '];'

    def shapesCode(self):
        code = []
        if self.stroke:
            code.append('wall('+self.pathName+','+self.height+','+self.width+');')
            if self.hasOuterFlare:
                code.append('  outerFlare('+self.pathName+');')
            elif self.hasInnerFlare:
                code.append('  innerFlare('+self.pathName+');')
        if self.fill:
            code.append('fill('+self.pathName+','+self.fillHeight+');')
        return '\n'.join(code) # + '\n'

class OuterWall(Line):
    def __init__(self, pathName, points, fill, stroke, strokeWidth):
        super(OuterWall, self).__init__(pathName, points, fill, stroke, strokeWidth)
        self.height = "wallHeight"
        self.width = "wallThickness(%.3f)" % self.strokeWidth
        self.fillHeight = "wallHeight"
        self.hasOuterFlare = True
        self.hasInnerFlare = False

class InnerWall(Line):
    def __init__(self, pathName, points, fill, stroke, strokeWidth):
        super(InnerWall, self).__init__(pathName, points, fill, stroke, strokeWidth)
        self.height = "wallHeight"
        self.width = "insideWallThickness(%.3f)" % self.strokeWidth
        self.fillHeight = "wallHeight"
        self.hasOuterFlare = False
        self.hasInnerFlare = True

class Feature(Line):
    def __init__(self, pathName, points, fill, stroke, strokeWidth):
        super(Feature, self).__init__(pathName, points, fill, stroke, strokeWidth)
        self.height = "featureHeight"
        self.width = "featureThickness(%.3f)" % self.strokeWidth
        self.fillHeight = "featureHeight"
        self.hasOuterFlare = False
        self.hasInnerFlare = False

class Connector(Line):
    def __init__(self, pathName, points, fill):
        super(Connector, self).__init__(pathName, points, fill, False, None) # no stroke for connectors, thus no use of self.height and self.width
        self.width = None
        self.fillHeight = "connectorThickness"
        self.hasOuterFlare = False
        self.hasInnerFlare = False

def svgToCookieCutter(filename, tolerance=0.1, strokeAll = False):
    lines = []
    pathCount = 0;
    minXY = [float("inf"), float("inf")]
    maxXY = [float("-inf"), float("-inf")]

    for superpath in parser.getPathsFromSVGFile(filename)[0]:
        for path in superpath.breakup():
            pathName = '_'+str(pathCount)
            pathCount += 1
            fill = path.svgState.fill is not None
            stroke = strokeAll or path.svgState.stroke is not None
            if not stroke and not fill: continue

            linearPath = path.linearApproximation(error=tolerance)
            points = [(-l.start.real,l.start.imag) for l in linearPath]
            points.append((-linearPath[-1].end.real, linearPath[-1].end.imag))

            if isRed    (path.svgState.fill) or isRed  (path.svgState.stroke):
                line = OuterWall('outerWall'+pathName, points, fill, stroke, path.svgState.strokeWidth)
            elif isGreen(path.svgState.fill) or isGreen(path.svgState.stroke):
                line = InnerWall('innerWall'+pathName, points, fill, stroke, path.svgState.strokeWidth)
            elif isBlack(path.svgState.fill) or isBlack(path.svgState.stroke):
                line = Feature  ('feature'  +pathName, points, fill, stroke, path.svgState.strokeWidth)
            else:
                line = Connector('connector'+pathName, points, fill)

            for i in range(2):
                minXY[i] = min(minXY[i], min(p[i] for p in line.points))
                maxXY[i] = max(maxXY[i], max(p[i] for p in line.points))
            lines.append(line)

    size = max(maxXY[0]-minXY[0], maxXY[1]-minXY[1])

    code = [PRELIM]
    code.append('// data from svg file')
    code += [line.pathCode()+'\n' for line in lines]
    code.append(
        '// main modules\n'
        'module cookieCutter() {')
    code += ['  ' + line.shapesCode() for line in lines]
    code.append('}\n')

    # demoulding plate module
    positives =        [line for line in lines if     isinstance(line, OuterWall) and line.stroke and not line.fill]
    negatives_stroke = [line for line in lines]
    negatives_fill   = [line for line in lines if not isinstance(line, OuterWall) and line.fill]
    code.append(
        "module demouldingPlate(){\n"
        "  // a plate to help push on the cookie to turn it out\n"
	"  render(convexity=10) difference() {\n"
	"    linear_extrude(height=demouldingPlateHeight) union() {")
    for line in positives:
        code.append('      polygon(points='+line.pathName+');')

    code.append("    }\n"
      "    translate([0,0,-0.01]) linear_extrude(height=demouldingPlateHeight+0.02) union() {")
    for line in negatives_stroke:
        code.append('      ribbon('+line.pathName+',thickness=demouldingPlateSlack'+('+'+line.width if line.stroke else '')+');')
    for line in negatives_fill:
        code.append('      polygon(points='+line.pathName+');')
        # TODO: we should remove the interior of polygonal inner walls
    code.append('    }\n  }\n}\n')

    code.append('////////////////////////////////////////////////////////////////////////////////')
    code.append('// final call, use main modules')
    code.append('translate([%.3f*scale + wallFlareWidth/2,  %.3f*scale + wallFlareWidth/2,0])'    % (-minXY[0],-minXY[1]))
    code.append('  cookieCutter();\n')

    code.append('// translate([-40,15,0]) cylinder(h=wallHeight+10,d=5,$fn=20); // handle')
    code.append('if (demouldingPlateHeight>0)')
    code.append('  mirror([1,0,0])')
    code.append('    translate([%.3f*scale + wallFlareWidth/2,  %.3f*scale + wallFlareWidth/2,0])' % (-minXY[0],-minXY[1]))
    code.append('      demouldingPlate();')

    return '\n'.join(code).replace('$OVERALL_SIZE$', '%.3f' % size)

if __name__ == '__main__':
    print(svgToCookieCutter(sys.argv[1]))
