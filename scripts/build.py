#!/usr/bin/env python3
"""Compile reviewed contract artifacts with the pinned Vyper compiler."""

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ABI_DIR = ROOT / "abi"
BUILD_DIR = ROOT / "build"
CONTRACTS = ("ChoiceBallot", "ChoiceBallotFactory")


def compile_output(contract: str, output_format: str) -> str:
    source = ROOT / "contracts" / f"{contract}.vy"
    return subprocess.check_output(
        ["vyper", "-f", output_format, str(source)],
        cwd=ROOT,
        text=True,
    ).strip()


def main() -> None:
    ABI_DIR.mkdir(exist_ok=True)
    BUILD_DIR.mkdir(exist_ok=True)

    for contract in CONTRACTS:
        abi = json.loads(compile_output(contract, "abi"))
        (ABI_DIR / f"{contract}.json").write_text(
            json.dumps(abi, indent=2) + "\n",
            encoding="utf-8",
        )
        (BUILD_DIR / f"{contract}.bytecode").write_text(
            compile_output(contract, "bytecode") + "\n",
            encoding="utf-8",
        )

    (BUILD_DIR / "ChoiceBallot.blueprint_bytecode").write_text(
        compile_output("ChoiceBallot", "blueprint_bytecode") + "\n",
        encoding="utf-8",
    )

    version = subprocess.check_output(["vyper", "--version"], text=True).strip()
    (BUILD_DIR / "compiler.txt").write_text(f"vyper {version}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
