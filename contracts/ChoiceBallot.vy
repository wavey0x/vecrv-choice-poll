#pragma version 0.4.3
#pragma evm-version cancun
#pragma optimize gas

import contracts.interfaces.IVotingEscrow as IVotingEscrow

VOTING_ESCROW: constant(address) = 0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2

MAX_CHOICES: constant(uint256) = 15
MAX_OPTIONS: constant(uint256) = 16
BPS: constant(uint256) = 10_000
FIRST_CHOICE_ID: constant(uint256) = 1

event VoteCast:
    voter: indexed(address)
    voter_weight: uint256
    allocations_hash: bytes32

title: public(String[64])
start_time: public(uint256)
end_time: public(uint256)
reference_block: public(uint256)
reference_supply: public(uint256)
quorum_bps: public(uint16)
choice_count: public(uint16)
option_count: public(uint16)

choices: DynArray[String[64], MAX_CHOICES]
has_voted: public(HashMap[address, bool])
option_scores: public(uint256[MAX_OPTIONS])
participating_weight: public(uint256)


@deploy
def __init__(
    title_: String[64],
    start_time_: uint256,
    end_time_: uint256,
    quorum_bps_: uint16,
    choice_names_: DynArray[String[64], MAX_CHOICES],
):
    assert len(title_) > 0, "empty title"
    assert start_time_ >= block.timestamp, "start in past"
    assert end_time_ > start_time_, "invalid window"
    assert len(choice_names_) >= 2, "too few choices"
    assert quorum_bps_ <= convert(BPS, uint16), "invalid quorum"
    assert block.number > 0, "invalid block"

    for i: uint256 in range(MAX_CHOICES):
        if i == len(choice_names_):
            break
        assert len(choice_names_[i]) > 0, "empty choice"
        for j: uint256 in range(MAX_CHOICES):
            if j == i:
                break
            assert choice_names_[i] != choice_names_[j], "duplicate choice"

    snapshot_block: uint256 = block.number - 1
    snapshot_supply: uint256 = staticcall IVotingEscrow(VOTING_ESCROW).totalSupplyAt(snapshot_block)
    assert snapshot_supply > 0, "zero supply"
    assert snapshot_supply <= max_value(uint256) // BPS, "supply overflow"

    self.title = title_
    self.start_time = start_time_
    self.end_time = end_time_
    self.reference_block = snapshot_block
    self.reference_supply = snapshot_supply
    self.quorum_bps = quorum_bps_
    self.choice_count = convert(len(choice_names_), uint16)
    self.option_count = convert(len(choice_names_) + FIRST_CHOICE_ID, uint16)
    self.choices = choice_names_


@external
@view
def choice_name(choice_id: uint16) -> String[64]:
    assert choice_id >= convert(FIRST_CHOICE_ID, uint16), "invalid choice"
    assert choice_id < self.option_count, "invalid choice"
    return self.choices[convert(choice_id, uint256) - FIRST_CHOICE_ID]


@external
def vote(allocations_bps: DynArray[uint16, MAX_OPTIONS]):
    assert block.timestamp >= self.start_time, "not started"
    assert block.timestamp < self.end_time, "ended"
    assert not self.has_voted[msg.sender], "already voted"
    assert len(allocations_bps) == convert(self.option_count, uint256), "wrong length"

    allocation_total: uint256 = 0
    for i: uint256 in range(MAX_OPTIONS):
        if i == len(allocations_bps):
            break
        allocation: uint256 = convert(allocations_bps[i], uint256)
        assert allocation <= BPS, "allocation too high"
        allocation_total += allocation
    assert allocation_total == BPS, "wrong total"

    weight: uint256 = staticcall IVotingEscrow(VOTING_ESCROW).balanceOfAt(
        msg.sender,
        self.reference_block,
    )
    assert weight > 0, "no voting power"

    self.has_voted[msg.sender] = True
    self.participating_weight += weight

    for i: uint256 in range(MAX_OPTIONS):
        if i == len(allocations_bps):
            break
        allocation: uint256 = convert(allocations_bps[i], uint256)
        if allocation > 0:
            self.option_scores[i] += weight * allocation

    log VoteCast(
        voter=msg.sender,
        voter_weight=weight,
        allocations_hash=keccak256(abi_encode(allocations_bps)),
    )


@external
@view
def quorum_reached() -> bool:
    return self.participating_weight * BPS >= self.reference_supply * convert(self.quorum_bps, uint256)


@external
@view
def result() -> (bool, bool, uint16):
    """
    @notice Return quorum status, tie status, and the winning eligible choice ID.
    @dev Reverts while voting is active. winner_id is zero without quorum or on a tie.
    """
    assert block.timestamp >= self.end_time, "still active"

    quorum_met: bool = self.participating_weight * BPS >= self.reference_supply * convert(self.quorum_bps, uint256)
    if not quorum_met:
        return False, False, 0

    winning_id: uint16 = convert(FIRST_CHOICE_ID, uint16)
    winning_score: uint256 = self.option_scores[FIRST_CHOICE_ID]
    tied: bool = False

    for i: uint256 in range(2, MAX_OPTIONS):
        if i == convert(self.option_count, uint256):
            break
        score: uint256 = self.option_scores[i]
        if score > winning_score:
            winning_score = score
            winning_id = convert(i, uint16)
            tied = False
        elif score == winning_score:
            tied = True

    if tied:
        return True, True, 0
    return True, False, winning_id
