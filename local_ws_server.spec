# -*- mode: python ; coding: utf-8 -*-

# PyInstaller spec file for local_ws_server.py

# Ensure 'websockets' and its dependencies are found.
# Common hidden imports for websockets and asyncio if not automatically detected.
# For websockets library, specific submodules might be needed depending on the version.
# 'websockets.legacy.server' and 'websockets.legacy.client' are common.
# 'asyncio' itself is usually handled, but sometimes specific platform backends might need help.
hidden_imports = [
    'websockets.legacy.server',
    'websockets.legacy.client',
    'websockets.extensions.permessage_deflate', # Common extension
    # Add other asyncio backends if needed for specific platforms, e.g.
    # 'asyncio.windows_events', 'asyncio.selector_events' (though usually not needed for basic asyncio.run)
]

a = Analysis(['local_ws_server.py'],
             pathex=['.'],  # Look for local_ws_server.py in the current directory
             binaries=[],
             datas=[],
             hiddenimports=hidden_imports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=None, # block_cipher variable was not defined, using None directly
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=None) # block_cipher variable was not defined

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='local_ws_server_executable', # Name of the output executable
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True, # UPX compression can reduce size but might affect startup or AV flags
          console=True) # console=True is important for stdio (like printing PORT:xxxx) and debugging

# For a one-directory bundle (simpler to manage, includes DLLs etc. alongside exe)
# coll = COLLECT(exe,
#                a.binaries,
#                a.zipfiles,
#                a.datas,
#                strip=False,
#                upx=True,
#                name='local_ws_server_dist') # Name of the output directory

# For a one-file bundle (more complex for PyInstaller, might be slower to start)
# The 'coll' part is not directly used if you just want the .exe from a one-file build,
# but PyInstaller still goes through this stage. If you want a true one-file, make sure
# the options in EXE are configured for it (often implied if no COLLECT stage is explicitly used
# to gather files into a directory).
# For one-file, you typically don't have a 'coll' that you distribute, just the 'exe'.
# The example provided seems to aim for a one-file build with the 'coll' being the final step
# if it were a one-dir build. For clarity, if one-file is intended, 'coll' is more of an intermediate name.
# The `name` in `COLLECT` is the name of the folder if creating a one-dir bundle.
# If `exe` is the primary target (one-file), this `COLLECT` stage describes where supporting files would go
# if it weren't a one-file build (or if `--onedir` was used).
# For a single executable, the `exe` object is what matters.
# The provided spec seems to use `name` in `COLLECT` as if it's for a one-dir build.
# If the goal is one-file, `coll` isn't the final product. If one-dir, it is.
# Let's assume the name in COLLECT is for the output directory if one-dir is used,
# but the primary target is the `exe` itself.
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='local_ws_server_dist') # This defines the folder if a one-dir build is made
                                       # For a one-file build, the exe is typically in dist/ directory directly or dist/<name_of_exe>/
                                       # For simplicity, the output executable will be in dist/local_ws_server_executable/
                                       # if using default PyInstaller structure with this spec, or just dist/local_ws_server_executable.exe
                                       # if --onefile is added to build command. The spec itself doesn't enforce onefile vs onedir.
                                       # The example `exe = EXE(...)` and `coll = COLLECT(exe, ...)` is standard.
                                       # The critical part is that `local_ws_server_executable` is created.
