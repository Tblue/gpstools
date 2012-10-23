#!/usr/bin/env python2
# Annotate a GPX 1.0 file.
#
# For each track, sets its description to the track's distance and
# optionally, renames the track.
#
# Exit codes:
#  0: Everything went fine.
#  1: Missing command line parameters.
#  2: Could not open input file.
#  3: Parse error in input file.
#  4: Input file is not a valid GPX file (or has wrong GPX version).
#  5: GPX file does not contain any tracks and/or points.
#  6: Could not write changes back.

### IMPORTS ###
import sys
import os
import shutil
import tempfile
from xml.etree import ElementTree
from gps import EarthDistance


### GLOBAL VARIABLES ###
# We only handle GPX 1.0 files for now.
gpxNamespaceURI = 'http://www.topografix.com/GPX/1/0'
gpxNamespace    = '{' + gpxNamespaceURI + '}'


### HELPER FUNCTIONS ###
def formatDistance( dist ):
    if dist >= 1000:
        return '%.2f km' % ( dist / 1000 )

    return '%.2f m' % dist


###################
### MAIN SCRIPT ###
###################

if len( sys.argv ) < 2:
    print >> sys.stderr, 'Usage:'
    print >> sys.stderr, ' %s gpx-file [new-track-name...]' % sys.argv[0]
    sys.exit( 1 )

# Setup namespace handling.
# This seems to make the GPX namespace the default, which is exactly
# what we want.
ElementTree.register_namespace( '', gpxNamespaceURI )

# Try to load and parse the GPX file:
try:
    gpxTree = ElementTree.ElementTree( None, sys.argv[1] )
except IOError as e:
    print >> sys.stderr, "E: Could not open file `%s': %s" \
            % (e.filename, e.strerror)
    sys.exit( 2 )
except ElementTree.ParseError as e:
    print >> sys.stderr, "E: Could not parse file `%s': %s" \
            % (sys.argv[1], e)
    sys.exit( 3 )

# Great, file parsed! Determine the GPX version:
gpxVer = gpxTree.getroot().get( 'version' )
if not gpxVer or not gpxTree.getroot().tag.endswith( '}gpx' ):
    print >> sys.stderr, "E: File `%s' does not appear to be a valid GPX file!" \
            % sys.argv[1]
    sys.exit( 4 )
elif gpxVer != '1.0':
    print >> sys.stderr, "E: File `%s' has unsupported GPX version %s (need: 1.0)." \
            % (sys.argv[1], gpxVer)
    sys.exit( 4 )

# Find all <trk> elements:
tracks = gpxTree.findall( gpxNamespace + 'trk' )
if len( tracks ) == 0:
    print >> sys.stderr, "E: No <trk> elements found in file `%s'!" \
            % sys.argv[1]
    sys.exit( 5 )

# Now, try to process each <trk> element:
for i in range( len( tracks ) ):
    track    = tracks[i]
    currname = track.findtext( gpxNamespace + 'name', '#' + str( i ) )

    points = track.findall( gpxNamespace + 'trkseg/' + gpxNamespace + 'trkpt' )
    if len( points ) == 0:
        # According to the spec, this is not an error.
        print >> sys.stderr, 'W: Track', currname, 'has no segments and/or points! Skipping.'
        continue

    # Calculate the distance of this track.
    distance = 0
    for j in range( 1, len( points ) ):
        aKeys = points[j-1].keys()
        bKeys = points[j].keys()

        if 'lat' not in aKeys or 'lon' not in aKeys or \
                'lat' not in bKeys or 'lon' not in bKeys:
            print >> sys.stderr, 'E: While processing track %s:' % currname, \
                    "<trkpt> is missing `lon' and/or `lat' attributes."
            sys.exit( 4 )

        try:
            pointA = (float( points[j-1].get( 'lat' ) ), float( points[j-1].get( 'lon' ) ))
            pointB = (float( points[j].get( 'lat' ) ), float( points[j].get( 'lon' ) ))
        except ValueError as e:
            print >> sys.stderr, 'E: While processing track %s:' % currname, \
                    "<trkpt> has invalid value for `lon' and/or `lat' attributes:", e
            sys.exit( 4 )

        distance += EarthDistance( pointA, pointB )

    # Now, make the distance this track's description:
    descElm = track.find( gpxNamespace + 'desc' )
    if descElm is None:
        descElm = ElementTree.SubElement( track, gpxNamespace + 'desc' )

    descElm.text = 'Distance: ' + formatDistance( distance )
    
    print 'Track %s:' % currname
    print '  Has distance %s.' % formatDistance( distance )

    if i + 2 < len( sys.argv ):
        # Rename track.
        print "  Renaming to `%s'." % sys.argv[i + 2]

        nameElm = track.find( gpxNamespace + 'name' )
        if nameElm is None:
            nameElm = ElementTree.SubElement( track, gpxNamespace + 'name' )

        nameElm.text = sys.argv[i + 2]

# Add some credit. :)
myName     = os.path.basename( sys.argv[0] )
gpxCreator = gpxTree.getroot().get( 'creator' )
if not gpxCreator:
    gpxCreator = myName
else:
    gpxCreator += ' (processed by %s)' % myName

gpxTree.getroot().set( 'creator', gpxCreator )

# First, write to a temporary file...
try:
    tmpFile = tempfile.NamedTemporaryFile()
    gpxTree.write( tmpFile, 'utf-8', True )
except IOError as e:
    print >> sys.stderr, "E: Could not create/write to temporary file `%s': %s" \
            % (e.filename, e.strerror)
    sys.exit( 6 )

# ...then copy the tempfile to the source file.
try:
    shutil.copyfile( tmpFile.name, sys.argv[1] )
except IOError as e:
    print >> sys.stderr, "E: Could not copy file `%s' to `%s': %s" \
            % (tmpFile.name, sys.argv[1], e.strerror)
    sys.exit( 6 )
