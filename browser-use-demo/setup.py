from setuptools import setup, find_packages

setup(
    name="browser-use-demo",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "streamlit==1.41.0",
        "anthropic[bedrock,vertex]>=0.39.0",
        "jsonschema==4.22.0",
        "boto3>=1.28.57",
        "google-auth<3,>=2",
        "playwright>=1.40.0",
    ],
    extras_require={
        "test": [
            "pytest==8.3.3",
            "pytest-cov==4.1.0",
            "pytest-mock==3.11.1",
            "pytest-asyncio==0.23.6",
        ],
        "dev": [
            "ruff==0.6.7",
            "pyright>=1.1.300",  
            "pre-commit==3.8.0",
        ],
    },
)
