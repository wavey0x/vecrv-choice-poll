import boa
import pytest


def test_choice_ids_are_contiguous_and_stable(create_ballot):
    ballot = create_ballot(choices=["No award", "LlamaRisk", "ChainSecurity"])

    assert ballot.choice_count() == 3
    assert [ballot.choice_name(i) for i in range(3)] == [
        "No award",
        "LlamaRisk",
        "ChainSecurity",
    ]
    assert ballot.choices() == (
        ["No award", "LlamaRisk", "ChainSecurity"],
        [0, 0, 0],
    )
    with boa.reverts("invalid choice"):
        ballot.choice_name(3)


@pytest.mark.parametrize(
    ("title", "choices", "quorum", "reason"),
    [
        ("", ["A", "B"], 0, "empty title"),
        ("Question", ["A"], 0, "too few choices"),
        ("Question", ["", "B"], 0, "empty choice"),
        ("Question", ["A", "A"], 0, "duplicate choice"),
        ("Question", ["A", "B"], 10_001, None),
    ],
)
def test_invalid_ballot_metadata_reverts(system, title, choices, quorum, reason):
    before = system.factory.ballot_count()
    error = boa.reverts(reason) if reason else pytest.raises(Exception)
    with boa.env.prank(system.accounts.creator):
        with error:
            system.factory.create_ballot(title, quorum, choices)
    assert system.factory.ballot_count() == before


def test_abi_rejects_oversized_title_and_choice(system):
    with boa.env.prank(system.accounts.creator):
        with pytest.raises(Exception):
            system.factory.create_ballot("x" * 65, 0, ["A", "B"])
        with pytest.raises(Exception):
            system.factory.create_ballot("Question", 0, ["x" * 65, "B"])


def test_choice_count_is_bounded_by_abi(system):
    with boa.env.prank(system.accounts.creator):
        with pytest.raises(Exception):
            system.factory.create_ballot(
                "Too many",
                0,
                [f"Choice {i}" for i in range(65)],
            )


def test_invalid_windows_revert_without_registration(system):
    now = boa.env.timestamp
    with boa.env.prank(system.accounts.creator):
        with boa.reverts("start in past"):
            system.factory.create_ballot("Past", 0, ["A", "B"], now - 1)
        with boa.reverts("invalid window"):
            system.factory.create_ballot("Same", 0, ["A", "B"], now, now)
        with boa.reverts("invalid window"):
            system.factory.create_ballot("Reverse", 0, ["A", "B"], now + 2, now + 1)
        with boa.reverts("window overflow"):
            system.factory.create_ballot(
                "Overflow",
                0,
                ["A", "B"],
                2**256 - 1,
            )
    assert system.factory.ballot_count() == 0


def test_zero_snapshot_supply_reverts(system):
    system.mock.set_default_supply(0)
    with boa.env.prank(system.accounts.creator):
        with boa.reverts("zero supply"):
            system.factory.create_ballot("Question", 0, ["A", "B"])
    assert system.factory.ballot_count() == 0


def test_snapshot_is_previous_block(system, create_ballot):
    creation_block = boa.env.evm.patch.block_number
    ballot = create_ballot()

    assert ballot.reference_block() == creation_block - 1
