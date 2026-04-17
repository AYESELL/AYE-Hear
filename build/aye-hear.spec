# -*- mode: python ; coding: utf-8 -*-
# HEAR-062: bundle Whisper model for offline ASR
# HEAR-094: upgraded from 'base' (~74MB) to 'small' (~244MB) for improved German ASR quality
import os as _os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
block_cipher = None
_whisper_model_dir = _os.path.join(_os.path.dirname(_os.path.abspath(SPEC)), '..', 'config', 'models', 'whisper', 'small')
_whisper_datas = [(_whisper_model_dir, 'models/whisper/small')] if _os.path.isfile(_os.path.join(_whisper_model_dir, 'model.bin')) else []

# Collect all psycopg submodules so SQLAlchemy's postgresql+psycopg dialect loads
# correctly in the frozen bundle (psycopg C-extension lives inside psycopg_binary).
_psycopg_imports = collect_submodules('psycopg') + collect_submodules('psycopg_binary')
_sqlalchemy_pg_imports = collect_submodules('sqlalchemy.dialects.postgresql')

a = Analysis(
    ['../src/ayehear/__main__.py'],
    pathex=['../src'],
    binaries=[],
    datas=[
        ('../config/', 'config'),
        ('../src/ayehear/storage/migrations/', 'ayehear/storage/migrations'),
    ] + _whisper_datas,
    # NOTE: faster_whisper Python code reaches the bundle via PYZ (auto-detected).
    # ctranslate2 DLLs + tokenizers are included via their PyInstaller hooks.
    # Whisper model staged by Build-WindowsPackage.ps1 -model staging- (HEAR-062).
    hiddenimports=[
        'ayehear.storage',
        'ayehear.storage.orm',
        'ayehear.storage.migrations',
        # psycopg3 + SQLAlchemy postgresql+psycopg dialect (all submodules required
        # for PyInstaller frozen bundle — static import discovery misses them).
        'psycopg',
        'psycopg.adapt',
        'psycopg.rows',
        'psycopg.types',
        'psycopg.types.numeric',
        'psycopg.types.text',
        'psycopg.types.date',
        'psycopg.types.array',
        'psycopg.types.composite',
        'psycopg.types.enum',
        'psycopg.types.net',
        'psycopg.types.range',
        'psycopg.types.multirange',
        'psycopg.types.json',
        'psycopg.pq',
        'psycopg._cmodule',
        'psycopg_binary',
        'sqlalchemy.dialects.postgresql',
        'sqlalchemy.dialects.postgresql.psycopg',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ] + _psycopg_imports + _sqlalchemy_pg_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pyannote.audio', 'silero_vad', 'ollama'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='AyeHear',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    uac_admin=False,
    icon='../assets/ayehear.ico',
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AyeHear',
)
