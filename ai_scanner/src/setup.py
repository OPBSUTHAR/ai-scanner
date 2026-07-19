from setuptools import setup, find_packages

setup(
    name="ai_scanner",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "scikit-image>=0.21.0",
        "scipy>=1.10.0",
        "pytesseract>=0.3.10",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-scanner=src.main:main",
        ],
    },
    python_requires=">=3.10",
)
