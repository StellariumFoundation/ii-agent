# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['stdio_echo.py'],
             pathex=['.'], # Current directory
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='stdio_echo_executable', # Output executable name
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True ) # Important: console=True for stdio
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='stdio_echo_dist') # Output directory for 'onedir' mode if used
