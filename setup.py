#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InevioNet - Guaranteed Delivery Protocol.

Bio-inspired decentralized P2P network.
"""
from setuptools import setup, find_packages
from pathlib import Path

this_dir = Path(__file__).parent
long_description = ""
readme_file = this_dir / "README.md"
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

version = "1.0.0"

setup(
    name="inevionet",
    version=version,
    author="InevioNet Team",
    author_email="info@inevionet.io",
    description="Guaranteed Delivery Protocol - 100% delivery through any network",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/inevionet/inevionet",
    license="MIT",
    packages=find_packages(
        exclude=["tests", "tests.*", "benchmarks", "benchmarks.*",
                 "examples", "examples.*"]),
    py_modules=["seed_server", "tcp_probe", "final_features"],
    # P9.5: inevionet_ext — пакет-обёртка для PyInstaller
    # (входит в packages через find_packages)
    python_requires=">=3.9",
    install_requires=[
        "cryptography>=41.0.0",
        "requests>=2.31.0",
        "websockets>=12.0",
        "scapy>=2.5.0",
        "flask>=3.0.0",
        "flask-socketio>=5.3.0",
        "python-socketio>=5.7.0",
        "eventlet>=0.33.0",
        "pyqrcode>=1.2.0",
        "pillow>=10.0.0",
        "paho-mqtt>=2.0.0",
        "pywifi>=1.1.12",
        "comtypes>=1.4.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.12.0",
            "flake8>=7.0.0",
            "mypy>=1.7.0",
        ],
        "drone": [
            "bleak>=0.22.0",
            "pyserial>=3.5",
        ],
    },
    entry_points={
        "console_scripts": [
            "inevionet-seed=seed_server:main",
            "inevionet-drone=drone.drone_client:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)