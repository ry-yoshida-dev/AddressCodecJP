import argparse
from typing import Protocol


class SubcommandRegistry(Protocol):
    """Sub-command group of an argument parser, as returned by ``add_subparsers``."""

    def add_parser(
        self, name: str, *, parents: list[argparse.ArgumentParser], help: str
    ) -> argparse.ArgumentParser:
        """
        Add the parser of a sub-command.

        Parameters
        ----------
        name : str
            Name of the sub-command.
        parents : list[argparse.ArgumentParser]
            Parsers whose arguments the sub-command shares.
        help : str
            Help of the sub-command in the command list.

        Returns
        -------
        argparse.ArgumentParser
            Parser of the sub-command.
        """
        ...
