from dataclasses import dataclass
from typing import List

@dataclass
class Account:
    mnemonic: List[str]
    address: str
    shard: int
    wallet_file: str
    pem_file: str
    balance: str = "0"

    def to_dict(self) -> dict:
        return {
            "mnemonic": self.mnemonic,
            "address": self.address,
            "shard": self.shard,
            "wallet_file": str(self.wallet_file),
            "pem_file": str(self.pem_file),
            "balance": self.balance
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Account':
        return cls(
            mnemonic=data["mnemonic"],
            address=data["address"],
            shard=data["shard"],
            wallet_file=data["wallet_file"],
            pem_file=data["pem_file"],
            balance=data["balance"]
        )
