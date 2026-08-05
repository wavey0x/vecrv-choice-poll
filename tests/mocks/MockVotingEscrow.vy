#pragma version 0.4.3
#pragma evm-version cancun

default_supply: public(uint256)
balances: public(HashMap[address, uint256])
supplies_at: public(HashMap[uint256, uint256])
balances_at: public(HashMap[address, HashMap[uint256, uint256]])


@external
def set_default_supply(supply: uint256):
    self.default_supply = supply


@external
def set_balance(account: address, balance: uint256):
    self.balances[account] = balance


@external
def set_supply_at(block_number: uint256, supply: uint256):
    self.supplies_at[block_number] = supply


@external
def set_balance_at(account: address, block_number: uint256, balance: uint256):
    self.balances_at[account][block_number] = balance


@external
@view
def totalSupplyAt(block_number: uint256) -> uint256:
    supply: uint256 = self.supplies_at[block_number]
    if supply == 0:
        return self.default_supply
    return supply


@external
@view
def balanceOfAt(account: address, block_number: uint256) -> uint256:
    balance: uint256 = self.balances_at[account][block_number]
    if balance == 0:
        return self.balances[account]
    return balance
