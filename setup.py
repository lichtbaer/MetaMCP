#!/usr/bin/env python3
"""
MCP Meta-Server Setup Configuration
"""

import os

# Read version from __init__.py
import re

from setuptools import find_packages, setup

with open(os.path.join("metamcp", "__init__.py")) as f:
    content = f.read()
    version_match = re.search(
        r'^__version__ = ["\']([^"\']*)["\']', content, re.MULTILINE
    )
    if version_match:
        version = {"__version__": version_match.group(1)}
    else:
        version = {"__version__": "0.0.0"}

# Read long description from README
with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="metamcp",
    version=version["__version__"],
    author="MetaMCP Team",
    author_email="team@metamcp.org",
    description="A dynamic MCP Meta-Server for AI agents with semantic tool discovery",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/MetaMCP",
    project_urls={
        "Bug Tracker": "https://github.com/your-org/MetaMCP/issues",
        "Documentation": "https://metamcp.readthedocs.io/",
        "Source Code": "https://github.com/your-org/MetaMCP",
        "Changelog": "https://github.com/your-org/MetaMCP/blob/main/CHANGELOG.md",
    },
    packages=find_packages(exclude=["tests*", "docs*", "examples*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
            "pre-commit>=3.6.0",
        ],
        "ui": [
            "streamlit>=1.28.1",
            "plotly>=5.17.0",
            "pandas>=2.1.3",
        ],
        "local-llm": [
            "ollama>=0.1.0",
            "transformers>=4.36.0",
            "torch>=2.1.0",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
            "sentry-sdk[fastapi]>=1.38.0",
        ],
        "all": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
            "pre-commit>=3.6.0",
            "streamlit>=1.28.1",
            "plotly>=5.17.0",
            "pandas>=2.1.3",
            "ollama>=0.1.0",
            "transformers>=4.36.0",
            "torch>=2.1.0",
            "prometheus-client>=0.19.0",
            "sentry-sdk[fastapi]>=1.38.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "metamcp=metamcp.cli:main",
            "metamcp-server=metamcp.main:main",
            "metamcp-admin=metamcp.admin.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "metamcp": [
            "policies/*.rego",
            "schemas/*.json",
            "templates/*.jinja2",
            "static/*",
        ],
    },
    zip_safe=False,
    keywords=[
        "mcp",
        "model-context-protocol",
        "ai",
        "artificial-intelligence",
        "agent",
        "tool",
        "proxy",
        "semantic-search",
        "vector-database",
        "weaviate",
        "fastapi",
        "llm",
        "openai",
    ],
)
