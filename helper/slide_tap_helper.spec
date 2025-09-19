# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Slide Tap Helper
This provides better control over the compilation process than command line options
"""

import sys
import os

# Get the helper directory (where this spec file is located)
helper_dir = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    ['main.py'],
    pathex=[helper_dir],
    binaries=[],
    datas=[
        ('config.example.json', '.'),
    ],
    hiddenimports=[
        # Firebase and Google Cloud
        'firebase_admin',
        'firebase_admin.credentials',
        'firebase_admin.firestore',
        'firebase_admin.storage',
        'google.cloud.firestore',
        'google.cloud.firestore_v1',
        'google.cloud.storage',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.oauth2',
        'google.oauth2.service_account',
        
        # Windows APIs
        'win32gui',
        'win32con',
        'win32api',
        'pywintypes',
        'pythoncom',
        
        # PySide6 components
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        
        # Other dependencies
        'mss',
        'mss.windows',
        'screeninfo',
        'PIL',
        'PIL.Image',
        'PIL.ImageGrab',
        'PIL._imaging',
        'PIL._imagingtk',
        'Pillow',
        
        # Standard library that PyInstaller might miss
        'json',
        'threading',
        'logging',
        'pathlib',
        'io',
        'time',
        'math',
        'datetime',
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        '_tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'jupyter',
        'IPython',
        'notebook',
        'tornado',
        'zmq',
        'sqlite3',
        'unittest',
        'test',
        'tests',
        'distutils',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='slide_tap_helper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress executable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging version
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',  # Will be created by GitHub Actions
)