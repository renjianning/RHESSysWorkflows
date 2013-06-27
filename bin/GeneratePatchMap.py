#!/usr/bin/env python
"""@package GeneratePatchMap

@brief Generate patch maps or in GRASS location associated with the project directory.

This software is provided free of charge under the New BSD License. Please see
the following license information:

Copyright (c) 2013, University of North Carolina at Chapel Hill
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of the University of North Carolina at Chapel Hill nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE UNIVERSITY OF NORTH CAROLINA AT CHAPEL HILL
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT 
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


@author Brian Miles <brian_miles@unc.edu>


Pre conditions
--------------
1. Configuration file must define the following sections and values:
   'GRASS', 'GISBASE'

2. The following metadata entry(ies) must be present in the study area section of the metadata associated with the project directory:
   dem_rows (if patch type is grid)

3. The following metadata entry(ies) must be present in the GRASS section of the metadata associated with the project directory:
   basin_rast
   dem_rast
   
4. The following metadata entry(ies) must be present in the RHESSys section of the metadata associated with the project directory:
   grass_dbase
   grass_location
   grass_mapset
   
Post conditions
---------------
1. Will write the following entry(ies) to the GRASS section of metadata associated with the project directory:
   patch_rast
 
Usage:
@code
GeneratePatchMap.py -p /path/to/project_dir
@endcode

@note EcoHydroWorkflowLib configuration file must be specified by environmental variable 'ECOHYDROWORKFLOW_CFG',
or -i option must be specified. 
"""
import os, sys, shutil
import argparse

from ecohydrolib.grasslib import *

from rhessysworkflows.context import Context
from rhessysworkflows.metadata import RHESSysMetadata

PATCH_RAST = 'patch'

# Handle command line options
parser = argparse.ArgumentParser(description='Generate patch maps or in GRASS location associated with the project directory.')
parser.add_argument('-i', '--configfile', dest='configfile', required=False,
                    help='The configuration file. Must define section "GRASS" and option "GISBASE"')
parser.add_argument('-p', '--projectDir', dest='projectDir', required=True,
                    help='The directory to which metadata, intermediate, and final files should be saved')
parser.add_argument('-t', '--patchType', dest='patchType', required=True, choices=['grid', 'clump'],
                    help='Type of patch to be generated: uniform grid or clumps based on elevation')
parser.add_argument('--overwrite', dest='overwrite', action='store_true', required=False,
                    help='Overwrite existing datasets in the GRASS mapset.  If not specified, program will halt if a dataset already exists.')
args = parser.parse_args()
cmdline = RHESSysMetadata.getCommandLine()

configFile = None
if args.configfile:
    configFile = args.configfile

context = Context(args.projectDir, configFile) 

# Check for necessary information in metadata
studyArea = RHESSysMetadata.readStudyAreaEntries(context)
if not 'dem_rows' in studyArea:
    sys.exit("Metadata in project directory %s does not contain DEM rows entry" % (context.projectDir,))
    
grassMetadata = RHESSysMetadata.readGRASSEntries(context)
if not 'basin_rast' in grassMetadata:
    sys.exit("Metadata in project directory %s does not contain a GRASS dataset with a basin raster" % (context.projectDir,))
if (args.patchType == 'clump') and (not 'dem_rast' in grassMetadata):
    sys.exit("Metadata in project directory %s does not contain a GRASS dataset with a DEM raster" % (context.projectDir,))

metadata = RHESSysMetadata.readRHESSysEntries(context)
if not 'grass_dbase' in metadata:
    sys.exit("Metadata in project directory %s does not contain a GRASS Dbase" % (context.projectDir,)) 
if not 'grass_location' in metadata:
    sys.exit("Metadata in project directory %s does not contain a GRASS location" % (context.projectDir,)) 
if not 'grass_mapset' in metadata:
    sys.exit("Metadata in project directory %s does not contain a GRASS mapset" % (context.projectDir,))

# Set up GRASS environment
modulePath = context.config.get('GRASS', 'MODULE_PATH')
grassDbase = os.path.join(context.projectDir, metadata['grass_dbase'])
grassConfig = GRASSConfig(context, grassDbase, metadata['grass_location'], metadata['grass_mapset'])
grassLib = GRASSLib(grassConfig=grassConfig)

# Make sure mask and region are properly set
demRast = grassMetadata['dem_rast']
result = grassLib.script.run_command('g.region', rast=demRast)
if result != 0:
    sys.exit("g.region failed to set region to DEM, returning %s" % (result,))

basinRast = grassMetadata['basin_rast']
result = grassLib.script.run_command('r.mask', flags='o', input=basinRast, maskcats='1')
if result != 0:
    sys.exit("r.mask failed to set mask to basin, returning %s" % (result,))

if args.patchType == 'grid':
    demRows = int(studyArea['dem_rows'])
    result = grassLib.script.write_command('r.mapcalc', 
                             stdin="%s=(row()-1) * %d + col()" % (PATCH_RAST, demRows) )
    if result != 0:
        sys.exit("r.mapcalc failed to create patch map, returning %s" % (result,))
    
if args.patchType == 'clump':
    result = grassLib.script.run_command('r.clump', input=demRast, output=PATCH_RAST, overwrite=args.overwrite)
    if result != 0:
        sys.exit("r.mapcalc failed to create patch map, returning %s" % (result,))

# Write metadata    
RHESSysMetadata.writeGRASSEntry(context, 'patch_rast', PATCH_RAST)

# Write processing history
RHESSysMetadata.appendProcessingHistoryItem(context, cmdline)