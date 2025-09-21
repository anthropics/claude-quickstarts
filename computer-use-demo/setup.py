from setuptools import setup, find_packages

setup(
    name="computer-use-demo",
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
)