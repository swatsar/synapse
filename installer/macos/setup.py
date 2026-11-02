"""
Synapse Agent - macOS App Bundle Setup

Protocol Version: 1.0
Spec Version: 3.1
"""

from setuptools import setup

APP = ['synapse/main.py']
DATA_FILES = [
    ('config', ['config/default.yaml']),
    ('skills', []),
]
OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'Synapse',
        'CFBundleDisplayName': 'Synapse Agent',
        'CFBundleIdentifier': 'org.synapse.agent',
        'CFBundleVersion': '3.1.0',
        'CFBundleShortVersionString': '3.1.0',
        'NSHumanReadableCopyright': 'Copyright 2026 Synapse Contributors',
        'NSHighResolutionCapable': True,
        'SynapseProtocolVersion': '1.0',
        'SynapseSpecVersion': '3.1',
    },
    'includes': [
        'pydantic',
        'litellm',
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'chromadb',
    ],
    'excludes': [
        'tkinter',
        'test',
        'unittest',
    ],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    name='Synapse',
    version='3.1.0',
    description='Universal Autonomous Agent Platform',
    author='Synapse Contributors',
)
