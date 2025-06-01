# ii_agent_backend.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000) # Often needed for complex apps

block_cipher = None

# --- Path to your application's entry point ---
entry_point = 'embedded_backend_main.py'

# --- Application Name (will be the name of the executable and output folder) ---
app_name = 'ii_agent_core_service'

# --- Collect data files ---
# Add tuples of (source_path_on_disk, destination_path_in_bundle)
# Example: If you have a 'prompts' directory in src/ii_agent/prompts
# datas = [('src/ii_agent/prompts', 'ii_agent/prompts')]
# This needs to be carefully reviewed for all non-Python files your agent/tools need.
# For now, let's assume the main prompts are part of the Python source or loaded via pkgutil.
# If not, they need to be listed here.
# Example: If src/ii_agent/prompts contains .txt files for prompts
# datas = [('src/ii_agent/prompts', 'ii_agent/prompts')]
# If your application uses .env files and you want to bundle a default one:
# datas = [('.env.example', '.env')]
datas = []

# --- Collect binaries ---
# If your tools or dependencies rely on external binaries (dlls, so, dylibs not automatically found)
# binaries = [('path/to/your/binary.dll', '.')]
# Example for playwright if it were used and needed manual browser binaries (though playwright often manages this itself)
# playwright_binaries = collect_playwright_binaries() # This would be a custom function
# binaries = playwright_binaries
binaries = []

# --- Hidden Imports ---
# Modules that PyInstaller might miss during its analysis.
# This list often grows during testing.
hidden_imports = [
    'uvloop', # Often used by FastAPI/Uvicorn, good to include if any part of it is pulled in by ii_agent code
    'httptools', # Companion to uvloop
    'websockets.legacy.server',
    'websockets.legacy.client',
    'websockets.extensions.permessage_deflate',
    'asyncio',
    'sqlalchemy.dialects.sqlite', # Default DB if no external one, or for testing
    'sqlalchemy.dialects.postgresql', # If PostgreSQL is an option
    'psycopg2', # If psycopg2-binary is used, sometimes just 'psycopg2' is needed here.
                # Or specific submodules like 'psycopg2._psycopg'
    'pydantic.v1', # If Pydantic v1 compatibility is used anywhere or by dependencies

    # Standard library modules that can sometimes be missed if dynamically imported
    'pkgutil',
    'importlib_metadata', # For Python < 3.8, for Python 3.8+ 'importlib.metadata'
    'json',
    'logging',
    'uuid',
    'socket',
    'pathlib',
    'argparse',
    'collections.abc', # For newer Python versions if type hints cause issues

    # Dependencies often used by web/api clients or data processing
    'charset_normalizer', # Often a dependency of requests
    'idna', # Dependency of requests
    'certifi', # SSL certificates

    # LLM SDKs and their dependencies if not fully picked up
    'anthropic',
    'anthropic._types',
    'anthropic.types',
    'openai',
    'tiktoken',
    'tiktoken_ext', # For OpenAI token counting
    'google.cloud.aiplatform',
    'google.auth',
    'google.oauth2',

    # Other common libraries from requirements.txt that might be tricky
    'anyio',
    'anyio._core._eventgroups', # Example of specific submodule
    'dotenv',
    'requests',
    'beautifulsoup4',
    'jsonschema',

    # If using Playwright (very large, ensure it's truly needed for embedded version)
    # 'playwright',
    # 'playwright.sync_api',
    # 'play_playwright._impl._driver', # Example of PyInstaller needing specific private modules

    # Database related if not directly imported
    # 'sqlite3' # Usually picked up

    # Add more based on testing and PyInstaller warnings/errors
]

# Remove duplicates if any were added manually and also by extend
hidden_imports = list(set(hidden_imports))


# --- Main Analysis ---
a = Analysis([entry_point],
             pathex=['.'], # Current directory where spec and entry_point are
             binaries=binaries,
             datas=datas,
             hiddenimports=hidden_imports,
             hookspath=[], # For custom PyInstaller hooks if needed
             runtime_hooks=[], # Scripts to run before your main script, e.g., for setting up env vars
             excludes=[], # Modules to explicitly exclude
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False) # noarchive=False is default, means create an archive for Python modules

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, # Typically just [entry_point]
          [], # Other scripts to bundle as exes (rarely used)
          exclude_binaries=True, # Exclude binaries from .exe, they go into COLLECT
          name=app_name, # Output executable name (without .exe)
          debug=False, # Set to True for debug builds (more verbose, larger)
          bootloader_ignore_signals=False,
          strip=False, # Strip symbols from executables and shared libs (set to True for release)
          upx=True, # UPX compression for exe and binaries (if upx is available on system)
          console=True, # Crucial: ensures stdio/stderr are available, needed for port printing
          # icon='path/to/your_icon.ico' # Optional: for Windows executable icon
          )

# --- Create a one-folder bundle (onedir) ---
# This collects the main executable (exe), its dependencies (binaries, Python modules in pyz),
# and any specified data files (datas) into a single output folder.
coll = COLLECT(exe,
               a.binaries, # Any non-Python shared libraries (.dll, .so, .dylib)
               a.zipfiles, # Python modules archive (pyz)
               a.datas,    # Data files specified above
               strip=False, # Strip symbols from collected binaries
               upx=True,    # Compress collected binaries with UPX
               upx_exclude=[], # List of binaries to exclude from UPX compression
               name=app_name) # This will be the name of the output folder in 'dist/'

# To build, run: pyinstaller ii_agent_backend.spec
# The output will be in dist/ii_agent_core_service/
# The executable will be dist/ii_agent_core_service/ii_agent_core_service (or .exe on Windows)
