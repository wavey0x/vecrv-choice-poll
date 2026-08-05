import os

import boa
import pytest

from conftest import VOTING_ESCROW


MAINNET_BLOCK = 22_000_000
CONVEX_VOTER_PROXY = "0x989AEb4d175e16225E39E87d0D97A3360524AD80"


@pytest.mark.fork
@pytest.mark.skipif(
    not os.environ.get("MAINNET_RPC_URL"),
    reason="MAINNET_RPC_URL is not configured",
)
def test_poll_reads_canonical_voting_escrow_on_fixed_mainnet_fork():
    boa.fork(os.environ["MAINNET_RPC_URL"], block_identifier=MAINNET_BLOCK)
    creator = boa.env.generate_address()
    poll_deployer = boa.load_partial("contracts/ChoicePoll.vy")
    blueprint = poll_deployer.deploy_as_blueprint()
    factory = boa.load(
        "contracts/ChoicePollFactory.vy",
        blueprint.address,
        [creator],
    )

    with boa.env.prank(creator):
        poll_address = factory.create_poll("Fork check", 0, ["A", "B"])
    poll = poll_deployer.at(poll_address)
    voting_escrow = boa.load_abi("tests/abi/IVotingEscrow.json").at(VOTING_ESCROW)

    assert poll.snapshot_supply() == voting_escrow.totalSupplyAt(
        poll.snapshot_block()
    )
    expected_weight = voting_escrow.balanceOfAt(
        CONVEX_VOTER_PROXY,
        poll.snapshot_block(),
    )
    assert expected_weight > 0

    with boa.env.prank(CONVEX_VOTER_PROXY):
        poll.vote([10_000, 0])
    assert poll.voted_supply() == expected_weight
