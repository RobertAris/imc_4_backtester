from abc import abstractmethod
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
import re
from typing import ContextManager, Optional


@contextmanager
def wrap_in_context_manager(value):
    yield value


class FileReader:
    @abstractmethod
    def file(self, path_parts: list[str]) -> ContextManager[Optional[Path]]:
        """Given a path to a file, yields a single Path object to the file or None if the file does not exist."""
        raise NotImplementedError()


class FileSystemReader(FileReader):
    def __init__(self, root: Path) -> None:
        self._root = root

    def file(self, path_parts: list[str]) -> ContextManager[Optional[Path]]:
        file = self._root
        for part in path_parts:
            file = file / part

        if not file.is_file():
            return wrap_in_context_manager(None)

        return wrap_in_context_manager(file)


class ImcDataReader(FileReader):
    def __init__(self, root: Path) -> None:
        self._root = root

    def file(self, path_parts: list[str]) -> ContextManager[Optional[Path]]:
        if len(path_parts) != 2:
            return wrap_in_context_manager(None)

        requested_file = path_parts[-1]
        candidates = self._candidate_paths(requested_file)
        for candidate in candidates:
            if candidate.is_file():
                return wrap_in_context_manager(candidate)

        return wrap_in_context_manager(None)

    def _candidate_paths(self, requested_file: str) -> list[Path]:
        match = re.fullmatch(r"(prices|trades|observations)_round_(\d+)_day_(-?\d+)\.csv", requested_file)
        if match is None:
            return [self._root / requested_file]

        file_type, round_num, day_num = match.groups()
        round_value = int(round_num)

        candidates = [self._root / requested_file]
        candidates.extend(self._round_directory_candidates(round_value, requested_file))

        if file_type == "prices":
            candidates.append(self._root / f"price_round_{round_num}_day_{day_num}_augmented.csv")

        return candidates

    def _round_directory_candidates(self, round_num: int, requested_file: str) -> list[Path]:
        directory_names = []
        if round_num == 0:
            directory_names.append("TUTORIAL")
        elif round_num == 1:
            directory_names.append("ROUND1")
        else:
            directory_names.extend(
                [
                    f"ROUND_{round_num}",
                    f"ROUND{round_num}",
                    f"round{round_num}",
                ]
            )

        return [self._root / directory_name / requested_file for directory_name in directory_names]


class PackageResourcesReader(FileReader):
    def file(self, path_parts: list[str]) -> ContextManager[Optional[Path]]:
        try:
            container = resources.files(f"prosperity4bt.resources.{'.'.join(path_parts[:-1])}")
            file = container / path_parts[-1]
            if not file.is_file():
                return wrap_in_context_manager(None)

            return resources.as_file(file)
        except Exception:
            return wrap_in_context_manager(None)
