#pragma version 0.4.3
#pragma evm-version cancun
#pragma optimize gas

import contracts.interfaces.IVotingEscrow as IVotingEscrow

VOTING_ESCROW: constant(address) = 0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2

MAX_CHOICES: constant(uint256) = 64
BPS: constant(uint256) = 10_000

event VoteCast:
    voter: indexed(address)
    voter_weight: uint256
    allocations_hash: bytes32

title: public(String[64])
start_time: public(uint256)
end_time: public(uint256)
snapshot_block: public(uint256)
snapshot_supply: public(uint256)
quorum_bps: public(uint16)
choice_count: public(uint16)

choice_labels: DynArray[String[64], MAX_CHOICES]
has_voted: public(HashMap[address, bool])
choice_scores: public(uint256[MAX_CHOICES])
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
    self.snapshot_block = snapshot_block
    self.snapshot_supply = snapshot_supply
    self.quorum_bps = quorum_bps_
    self.choice_count = convert(len(choice_names_), uint16)
    self.choice_labels = choice_names_


@external
@view
def choice_name(choice_id: uint16) -> String[64]:
    assert choice_id < self.choice_count, "invalid choice"
    return self.choice_labels[convert(choice_id, uint256)]


@external
@view
def choices() -> (DynArray[String[64], MAX_CHOICES], DynArray[uint256, MAX_CHOICES]):
    scores: DynArray[uint256, MAX_CHOICES] = []
    for i: uint256 in range(MAX_CHOICES):
        if i == convert(self.choice_count, uint256):
            break
        scores.append(self.choice_scores[i])
    return self.choice_labels, scores


@external
def vote(allocations_bps: DynArray[uint16, MAX_CHOICES]):
    assert block.timestamp >= self.start_time, "not started"
    assert block.timestamp < self.end_time, "ended"
    assert not self.has_voted[msg.sender], "already voted"
    assert len(allocations_bps) == convert(self.choice_count, uint256), "wrong length"

    allocation_total: uint256 = 0
    for i: uint256 in range(MAX_CHOICES):
        if i == len(allocations_bps):
            break
        allocation: uint256 = convert(allocations_bps[i], uint256)
        assert allocation <= BPS, "allocation too high"
        allocation_total += allocation
    assert allocation_total == BPS, "wrong total"

    weight: uint256 = staticcall IVotingEscrow(VOTING_ESCROW).balanceOfAt(
        msg.sender,
        self.snapshot_block,
    )
    assert weight > 0, "no voting power"

    self.has_voted[msg.sender] = True
    self.participating_weight += weight

    for i: uint256 in range(MAX_CHOICES):
        if i == len(allocations_bps):
            break
        allocation: uint256 = convert(allocations_bps[i], uint256)
        if allocation > 0:
            self.choice_scores[i] += weight * allocation

    log VoteCast(
        voter=msg.sender,
        voter_weight=weight,
        allocations_hash=keccak256(abi_encode(allocations_bps)),
    )


@internal
@view
def _quorum_reached() -> bool:
    return self.participating_weight * BPS >= self.snapshot_supply * convert(self.quorum_bps, uint256)


@external
@view
def quorum_reached() -> bool:
    return self._quorum_reached()


@external
@view
def winner() -> (bool, uint16):
    if block.timestamp < self.end_time or not self._quorum_reached():
        return False, 0

    winning_id: uint16 = 0
    winning_score: uint256 = self.choice_scores[0]
    tied: bool = False

    for i: uint256 in range(1, MAX_CHOICES):
        if i == convert(self.choice_count, uint256):
            break
        score: uint256 = self.choice_scores[i]
        if score > winning_score:
            winning_score = score
            winning_id = convert(i, uint16)
            tied = False
        elif score == winning_score:
            tied = True

    if tied:
        return False, 0
    return True, winning_id
