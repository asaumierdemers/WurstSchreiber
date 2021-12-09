'''build Wurst Schreiber'''

import os
from pathlib import Path
from mojo.extensions import ExtensionBundle

# get current folder
basePath = Path.cwd()

# source folder for all extension files
sourcePath = os.path.join(basePath, 'source')

# folder with python files
libPath = basePath / 'source' / 'code'

# name of the compiled extension file
extensionFile = 'WurstSchreiber.roboFontExt'

# path of the compiled extension
extensionPath = basePath / extensionFile

# initiate the extension builder
B = ExtensionBundle()

# name of the extension
B.name = "Wurst Schreiber"

# name of the developer
B.developer = 'Alexandre Saumier Demers'

# URL of the developer
B.developerURL = 'http://asaumierdemers.com'

# version of the extension
B.version = '1.2'

# should the extension be launched at start-up?
B.launchAtStartUp = True

# script to be executed when RF starts
B.mainScript = 'events.py'

# does the extension contain html help files?
B.html = False

# minimum RoboFont version required for this extension
B.requiresVersionMajor = '4'
B.requiresVersionMinor = '1'

# scripts which should appear in Extensions menu
B.addToMenu = [
    {
        'path':          'WurstSchreiber.py',
        'preferredName': 'Wurst Schreiber',
        'shortKey':      '',
    },
]

# compile and save the extension bundle
print('building extension...', end=' ')
B.save(extensionPath, libPath=os.fspath(libPath))
print('done!')

# check for problems in the compiled extension
print()
print(B.validationErrors())
