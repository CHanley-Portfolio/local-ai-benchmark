"""
Load versioned local benchmark context fixtures.

Context fixtures provide controlled project/document context for benchmark
cases that need information beyond the benchmark prompt itself.
"""

from pathlib import Path


class BenchmarkContextFixtureLoader:
    """
    Load benchmark context fixtures from one configured directory.

    The loader deliberately owns filesystem access so application services 
    do not need to know where benchmark fixtures are stored.

    Fixture names are treated as filenames relative to the configured fixture directory.
    Paths that escape that directory are rejected.
    """

    def __init__(self, fixture_directory: Path) -> None:
        """
        Create a context fixture loader.

        Args:
            fixture_directory:
                Directory containing versioned benchmark fixture files.
        """

        self._fixture_directory = fixture_directory.resolve()

    def load(self, fixture_name: str) -> str:
        """
        Load one benchmark context fixture as UTF-8 text.

        Args:
            fixture_name:
                Filename stored by the benchmark-case definition, such as 'project_database_decision_v1.md'

        Returns:
            str:
                Complete fixture contents.

        Raises:
            ValueError:
                Raised when the fixture name is blank or resolves outside the configured fixture directory.

            FileNotFoundError:
                raised when the requested fixture does not exist.
        """

        if not fixture_name.strip():
            raise ValueError("Benchmark context fixture name must not be blank.")

        fixture_path = (self._fixture_directory / fixture_name).resolve()

        if fixture_path.parent != self._fixture_directory:
            raise ValueError("Benchmark context fixture must be located directly inside the configured fixture directory.")

        if not fixture_path.is_file():
            raise FileNotFoundError(f"Benchmark context fixture '{fixture_name}' does not exist in '{self._fixture_directory}'.")

        return fixture_path.read_text(encoding="utf-8")