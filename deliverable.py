"""
Staking Pool Reward Distributor and Epoch Balance Snapshotter

This module provides a pure Python reference implementation for a staking pool reward distributor and an epoch balance snapshotter,
as described in https://github.com/solana-labs/solana-program-library/issues/402.

This code is intended as a clean, modular, production-ready reference for logic and testability.
It does NOT interact with Solana on-chain programs, but models the core logic for reward distribution and epoch snapshots.

Author: OpenAI Assistant
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import math


@dataclass
class StakeAccount:
    """Represents a user's stake account in the pool."""
    owner: str
    balance: int  # lamports


@dataclass
class EpochSnapshot:
    """Snapshot of all stake balances at a given epoch."""
    epoch: int
    total_staked: int
    balances: Dict[str, int]  # owner -> balance


@dataclass
class RewardDistribution:
    """Represents a reward distribution for an epoch."""
    epoch: int
    total_reward: int
    rewards: Dict[str, int]  # owner -> reward


class StakingPool:
    """
    Staking Pool with reward distribution and epoch balance snapshotting.
    """
    def __init__(self) -> None:
        self.stake_accounts: Dict[str, StakeAccount] = {}
        self.epoch_snapshots: Dict[int, EpochSnapshot] = {}
        self.reward_distributions: Dict[int, RewardDistribution] = {}
        self.current_epoch: int = 0

    def deposit(self, owner: str, amount: int) -> None:
        """
        Deposit lamports into the staking pool for a given owner.
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        if owner not in self.stake_accounts:
            self.stake_accounts[owner] = StakeAccount(owner=owner, balance=0)
        self.stake_accounts[owner].balance += amount

    def withdraw(self, owner: str, amount: int) -> None:
        """
        Withdraw lamports from the staking pool for a given owner.
        """
        if amount <= 0:
            raise ValueError("Withdraw amount must be positive")
        if owner not in self.stake_accounts or self.stake_accounts[owner].balance < amount:
            raise ValueError("Insufficient balance")
        self.stake_accounts[owner].balance -= amount

    def snapshot_epoch(self, epoch: Optional[int] = None) -> None:
        """
        Take a snapshot of all balances at the current or specified epoch.
        """
        if epoch is None:
            epoch = self.current_epoch
        balances = {owner: acct.balance for owner, acct in self.stake_accounts.items() if acct.balance > 0}
        total_staked = sum(balances.values())
        self.epoch_snapshots[epoch] = EpochSnapshot(
            epoch=epoch,
            total_staked=total_staked,
            balances=balances
        )

    def distribute_rewards(self, epoch: int, total_reward: int) -> RewardDistribution:
        """
        Distribute rewards for a given epoch, based on the snapshot taken at that epoch.
        Rewards are distributed proportionally to staked balances at the snapshot.
        """
        if total_reward <= 0:
            raise ValueError("Total reward must be positive")
        if epoch not in self.epoch_snapshots:
            raise ValueError(f"No snapshot for epoch {epoch}")
        snapshot = self.epoch_snapshots[epoch]
        if snapshot.total_staked == 0:
            raise ValueError("No staked balance to distribute rewards")
        rewards: Dict[str, int] = {}
        distributed = 0
        # Calculate raw rewards and round down, keep track of remainder
        for owner, balance in snapshot.balances.items():
            reward = (balance * total_reward) // snapshot.total_staked
            rewards[owner] = reward
            distributed += reward
        # Distribute any remainder to largest stakers
        remainder = total_reward - distributed
        if remainder > 0:
            # Sort owners by balance descending
            sorted_owners = sorted(snapshot.balances.items(), key=lambda x: (-x[1], x[0]))
            for i in range(remainder):
                owner = sorted_owners[i % len(sorted_owners)][0]
                rewards[owner] += 1
        self.reward_distributions[epoch] = RewardDistribution(
            epoch=epoch,
            total_reward=total_reward,
            rewards=rewards
        )
        return self.reward_distributions[epoch]

    def advance_epoch(self) -> None:
        """
        Advance to the next epoch and take a snapshot.
        """
        self.current_epoch += 1
        self.snapshot_epoch(self.current_epoch)

    def get_snapshot(self, epoch: int) -> Optional[EpochSnapshot]:
        """
        Get the snapshot for a given epoch.
        """
        return self.epoch_snapshots.get(epoch)

    def get_reward_distribution(self, epoch: int) -> Optional[RewardDistribution]:
        """
        Get the reward distribution for a given epoch.
        """
        return self.reward_distributions.get(epoch)

    def get_owner_balance(self, owner: str) -> int:
        """
        Get the current balance for an owner.
        """
        return self.stake_accounts.get(owner, StakeAccount(owner, 0)).balance

    def apply_rewards(self, epoch: int) -> None:
        """
        Apply the distributed rewards for an epoch to the stake accounts.
        """
        distribution = self.get_reward_distribution(epoch)
        if distribution is None:
            raise ValueError(f"No reward distribution for epoch {epoch}")
        for owner, reward in distribution.rewards.items():
            if owner not in self.stake_accounts:
                self.stake_accounts[owner] = StakeAccount(owner=owner, balance=0)
            self.stake_accounts[owner].balance += reward

    def get_total_staked(self) -> int:
        """
        Get the total staked balance in the pool.
        """
        return sum(acct.balance for acct in self.stake_accounts.values())

    def get_all_balances(self) -> Dict[str, int]:
        """
        Get all current balances.
        """
        return {owner: acct.balance for owner, acct in self.stake_accounts.items() if acct.balance > 0}


# ------------------- TESTS -------------------

def _test_staking_pool() -> None:
    pool = StakingPool()
    pool.deposit("alice", 1000)
    pool.deposit("bob", 2000)
    pool.deposit("carol", 7000)
    assert pool.get_total_staked() == 10000
    pool.snapshot_epoch(1)
    snap = pool.get_snapshot(1)
    assert snap is not None
    assert snap.total_staked == 10000
    assert snap.balances == {"alice": 1000, "bob": 2000, "carol": 7000}
    # Distribute 1000 reward
    dist = pool.distribute_rewards(1, 1000)
    assert dist.total_reward == 1000
    # Rewards: alice 100, bob 200, carol 700
    assert dist.rewards["alice"] == 100
    assert dist.rewards["bob"] == 200
    assert dist.rewards["carol"] == 700
    # Apply rewards
    pool.apply_rewards(1)
    assert pool.get_owner_balance("alice") == 1100
    assert pool.get_owner_balance("bob") == 2200
    assert pool.get_owner_balance("carol") == 7700
    # Withdraw
    pool.withdraw("carol", 700)
    assert pool.get_owner_balance("carol") == 7000
    # Advance epoch and snapshot
    pool.advance_epoch()
    snap2 = pool.get_snapshot(2)
    assert snap2 is not None
    assert snap2.total_staked == 10300
    # Distribute 103 reward
    dist2 = pool.distribute_rewards(2, 103)
    # Rewards should sum to 103
    assert sum(dist2.rewards.values()) == 103
    # Remainder distributed to largest stakers
    rewards_sorted = sorted(dist2.rewards.items(), key=lambda x: -x[1])
    assert rewards_sorted[0][1] >= rewards_sorted[-1][1]
    print("All tests passed.")


if __name__ == "__main__":
    _test_staking_pool()