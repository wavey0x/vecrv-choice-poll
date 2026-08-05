#!/usr/bin/env python3
"""Compile reviewed contract artifacts with the pinned Vyper compiler."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
CONTRACTS = ("ChoicePoll", "ChoicePollFactory")


def compile_output(contract: str, output_format: str) -> str:
    source = ROOT / "contracts" / f"{contract}.vy"
    return subprocess.check_output(
        ["vyper", "-f", output_format, str(source)],
        cwd=ROOT,
        text=True,
    ).strip()


def main() -> None:
    BUILD_DIR.mkdir(exist_ok=True)

    for contract in CONTRACTS:
        (BUILD_DIR / f"{contract}.bytecode").write_text(
            compile_output(contract, "bytecode") + "\n",
            encoding="utf-8",
        )

    (BUILD_DIR / "ChoicePoll.blueprint_bytecode").write_text(
        compile_output("ChoicePoll", "blueprint_bytecode") + "\n",
        encoding="utf-8",
    )

    version = subprocess.check_output(["vyper", "--version"], text=True).strip()
    (BUILD_DIR / "compiler.txt").write_text(f"vyper {version}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
