#!/usr/bin/env python3
"""Deploy the immutable poll blueprint and factory to Ethereum mainnet."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boa
from eth_account import Account
from eth_utils import is_address, to_checksum_address


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--creator",
        action="append",
        required=True,
        help="Initial trusted creator address; repeat for each multisig (maximum 8)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "deployments" / "mainnet.json",
        help="Deployment record path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rpc_url = os.environ.get("MAINNET_RPC_URL")
    private_key = os.environ.get("DEPLOYER_PRIVATE_KEY")
    if not rpc_url or not private_key:
        raise SystemExit("MAINNET_RPC_URL and DEPLOYER_PRIVATE_KEY are required")
    if not 1 <= len(args.creator) <= 8:
        raise SystemExit("Provide between one and eight initial creators")
    if any(not is_address(creator) for creator in args.creator):
        raise SystemExit("Every creator must be a valid Ethereum address")
    creators = [to_checksum_address(creator) for creator in args.creator]
    if len(set(creators)) != len(creators):
        raise SystemExit("Initial creators must be unique")
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing deployment record: {args.output}")

    account = Account.from_key(private_key)
    boa.set_network_env(rpc_url)
    chain_id = int(boa.env._rpc.fetch("eth_chainId", []), 16)
    if chain_id != 1:
        raise SystemExit(f"Expected Ethereum mainnet (chain 1), received chain {chain_id}")
    boa.env.add_account(account, force_eoa=True)

    poll_deployer = boa.load_partial(ROOT / "contracts" / "ChoicePoll.vy")
    blueprint = poll_deployer.deploy_as_blueprint()
    factory = boa.load(
        ROOT / "contracts" / "ChoicePollFactory.vy",
        blueprint.address,
        creators,
    )
    if factory.poll_blueprint() != blueprint.address:
        raise RuntimeError("Factory blueprint verification failed")
    if not all(factory.approved_creators(creator) for creator in creators):
        raise RuntimeError("Initial creator verification failed")

    record = {
        "chain_id": chain_id,
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "deployer": account.address,
        "choice_poll_blueprint": str(blueprint.address),
        "choice_poll_factory": str(factory.address),
        "initial_creators": creators,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
