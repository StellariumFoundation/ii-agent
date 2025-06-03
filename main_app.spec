# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

block_cipher = None

# --- Basic Analysis ---
a = Analysis(
    ['main_app.py'],
    pathex=['.', str(Path('src'))],  # Current directory and src
    binaries=[],
    datas=[],     # Will be populated below
    hiddenimports=[
        'uvicorn.lifespan.on',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'fastapi.applications',
        'pydantic.v1',
        'anthropic',
        'anthropic.lib',
        'anthropic._tokenizers.tokenizer', # More specific attempt
        'google.api_core',
        'google.auth',
        'google.cloud.aiplatform',
        'sqlalchemy.dialects.sqlite',
        'importlib_metadata',
        'playwright',
        'playwright.sync_api',
        'playwright._impl',
        'duckduckgo_search',
        'tavily',
        'pandas',
        'numpy',
        'pyarrow',
        'charset_normalizer',
        'h11',
        'yaml',
        'jinja2',
    ],
    hookspath=['.'],  # Directory containing custom hooks (hook-anthropic.py)
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Include Data Files ---
# Temporarily commenting out frontend/out to isolate ValueError
# frontend_out_path = Path('frontend/out')
# if frontend_out_path.is_dir():
#     a.datas += [
#         (str(frontend_out_path), 'frontend/out')
#     ]
# else:
#     print(f"WARNING: '{frontend_out_path}' directory not found. Frontend won't be bundled.", file=sys.stderr)

# --- Executable ---
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='II-Agent-App',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# --- Bundle (One-Directory Mode) ---
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas, # This will be empty for now
    strip=False,
    upx=True,
    upx_exclude=[],
    name='II-Agent-App-Bundle',
)
