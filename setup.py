from setuptools import setup, find_packages

setup(
    name="erp-sync-poc",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "asyncpg>=0.29.0",
        "python-dotenv>=1.0.0",
        "alembic>=1.12.0",
        "tabulate>=0.9.0",
        "colorama>=0.4.6",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ]
    },
    python_requires=">=3.10",
)