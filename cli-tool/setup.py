from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="deploy-tool",  
    version="1.0.0",
    author="Uzaif",
    author_email="uzaif@example.com",
    description="Vercel-like CLI tool for AWS S3 deployment - DevOps Capstone Project",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/uzaif/deploy-tool",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "boto3>=1.26.0",
        "docker>=6.0.0",
        "gitpython>=3.1.0",
        "colorama>=0.4.0",
    ],
    entry_points={
        "console_scripts": [
            "deploy-tool=deploy_tool.cli:cli",  
        ],
    },
)
