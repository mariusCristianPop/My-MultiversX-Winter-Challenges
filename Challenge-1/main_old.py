from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import time
from dotenv import load_dotenv
import os
import logging
import json
from multiversx_sdk import (
    Address, Mnemonic, UserWallet, UserPEM, AddressComputer,
    ProxyNetworkProvider, Transaction, AccountNonceHolder,
    TransactionComputer, UserSigner
)

load_dotenv()

def setup_logging(output_dir: Path) -> logging.Logger:
    # Create output directory first
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up logger
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"execution_log_{timestamp}.txt"
    logger = logging.getLogger("ShardWalletOrchestrator")
    logger.propagate = False

    # Clear any existing handlers
    logger.handlers = []

    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_format)
    logger.addHandler(console_handler)

    return logger

# config.py
from dataclasses import dataclass
from pathlib import Path

# Network settings
PROXY_URL = os.getenv("PROXY_URL")
CHAIN_ID = os.getenv("CHAIN_ID")
NUM_SHARDS = int(os.getenv("NUM_SHARDS"))
GAS_LIMIT = int(os.getenv("GAS_LIMIT"))
FUNDING_AMOUNT = os.getenv("FUNDING_AMOUNT")
TRANSACTION_DELAY = int(os.getenv("TRANSACTION_DELAY"))
BALANCE_QUERY_DELAY = int(os.getenv("BALANCE_QUERY_DELAY"))
BALANCE_QUERY_RETRIES = int(os.getenv("BALANCE_QUERY_RETRIES"))
POST_FUNDING_WAIT = int(os.getenv("POST_FUNDING_WAIT"))

# Wallet settings
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR"))
NUM_ACCOUNTS_PER_SHARD = int(os.getenv("NUM_ACCOUNTS_PER_SHARD"))
WALLET_PASSWORD = os.getenv("WALLET_PASSWORD")
FUNDING_WALLET_PEM = Path(os.getenv("FUNDING_WALLET_PEM"))

# File paths
ACCOUNTS_INFO_FILE = os.getenv("ACCOUNTS_INFO_FILE")
TEMP_WALLET_FILE = os.getenv("TEMP_WALLET_FILE")

@dataclass
class NetworkConfig:
    proxy_url: str
    chain_id: str
    num_shards: int
    min_gas_limit: int = GAS_LIMIT
    funding_amount: str = FUNDING_AMOUNT
    transaction_delay: int = TRANSACTION_DELAY
    balance_query_delay: int = BALANCE_QUERY_DELAY
    balance_query_retries: int = BALANCE_QUERY_RETRIES
    post_funding_wait: int = POST_FUNDING_WAIT

@dataclass
class WalletConfig:
    output_dir: Path
    num_accounts_per_shard: int
    password: str
    network: NetworkConfig

# exceptions.py
class WalletGenerationError(Exception):
    """Base exception for wallet generation errors"""
    pass

class FundingError(Exception):
    """Exception for funding-related errors"""
    pass

class BalanceQueryError(Exception):
    """Exception for balance query errors"""
    pass

# models.py
from typing import List, Dict
from dataclasses import dataclass

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

# wallet_managers.py
from typing import Optional
import time
import json

class FundingWalletManager:
    def __init__(self, config: NetworkConfig, pem_path: Path, logger: logging.Logger):
        self.config = config
        self.provider = ProxyNetworkProvider(config.proxy_url)
        self.signer = UserSigner.from_pem_file(pem_path)
        self.address = self.signer.get_pubkey().to_address("erd")
        self.transaction_computer = TransactionComputer()
        self.logger = logger

    def fund_account(self, receiver: str) -> str:
        try:
            account = self.provider.get_account(self.address)
            nonce_holder = AccountNonceHolder(account.nonce)

            tx = Transaction(
                nonce=nonce_holder.get_nonce_then_increment(),
                sender=self.address.to_bech32(),
                receiver=receiver,
                value=self.config.funding_amount,
                gas_limit=self.config.min_gas_limit,
                chain_id=self.config.chain_id
            )

            tx.signature = self.signer.sign(self.transaction_computer.compute_bytes_for_signing(tx))
            return self.provider.send_transaction(tx)
        except Exception as e:
            self.logger.error(f"Failed to fund account {receiver}: {str(e)}")
            raise FundingError(f"Failed to fund account {receiver}: {str(e)}")

class WalletGenerator:
    def __init__(self, config: WalletConfig, logger: logging.Logger):
        self.config = config
        self.address_computer = AddressComputer(number_of_shards=config.network.num_shards)
        self.provider = ProxyNetworkProvider(config.network.proxy_url)
        self.logger = logger
        self._create_directories()

    def _create_directories(self):
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        for shard in range(self.config.network.num_shards):
            (self.config.output_dir / f"shard_{shard}").mkdir(parents=True, exist_ok=True)

    def generate_account(self) -> Account:
        mnemonic = Mnemonic.generate()
        wallet = UserWallet.from_mnemonic(mnemonic.get_text(), self.config.password)
        temp_path = self.config.output_dir / TEMP_WALLET_FILE

        try:
            wallet.save(temp_path)
            secret_key = UserWallet.load_secret_key(temp_path, self.config.password)
            address = secret_key.generate_public_key().to_address("erd")
            shard = self.address_computer.get_shard_of_address(address)

            base_name = f"wallet_{address.to_bech32()[:8]}"
            shard_dir = self.config.output_dir / f"shard_{shard}"

            wallet_path = shard_dir / f"{base_name}.json"
            pem_path = shard_dir / f"{base_name}.pem"

            temp_path.rename(wallet_path)
            self._generate_pem(address, secret_key, pem_path)

            return Account(
                mnemonic=mnemonic.get_words(),
                address=address.to_bech32(),
                shard=shard,
                wallet_file=str(wallet_path),
                pem_file=str(pem_path)
            )
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            self.logger.error(f"Failed to generate wallet: {str(e)}")
            raise WalletGenerationError(f"Failed to generate wallet: {str(e)}")

    def _generate_pem(self, address: Address, secret_key, filepath: Path):
        pem = UserPEM(label=address.to_bech32(), secret_key=secret_key)
        pem.save(filepath)

# main.py
class ShardWalletOrchestrator:
    def __init__(self, config: WalletConfig, funding_pem_path: Path):
        self.config = config
        self.provider = ProxyNetworkProvider(config.network.proxy_url)
        self.logger = setup_logging(config.output_dir)
        self.wallet_generator = WalletGenerator(config, self.logger)
        self.funding_manager = FundingWalletManager(config.network, funding_pem_path, self.logger)
        self.accounts: Dict[int, List[Account]] = {i: [] for i in range(config.network.num_shards)}

    def generate_accounts(self):
        for target_shard in range(self.config.network.num_shards):
            while len(self.accounts[target_shard]) < self.config.num_accounts_per_shard:
                account = self.wallet_generator.generate_account()
                if account.shard == target_shard:
                    self.accounts[target_shard].append(account)
                    self._log_account_generation(account)

    def fund_accounts(self):
        for accounts in self.accounts.values():
            for account in accounts:
                tx_hash = self.funding_manager.fund_account(account.address)
                self._log_funding(account, tx_hash)
                time.sleep(self.config.network.transaction_delay)

    def update_balances(self):
        for accounts in self.accounts.values():
            for account in accounts:
                account.balance = self._get_account_balance(account.address)
                time.sleep(self.config.network.balance_query_delay)

    def save_accounts_info(self):
        output_file = self.config.output_dir / ACCOUNTS_INFO_FILE
        output_data = {
            f"shard_{shard}": [account.to_dict() for account in accounts]
            for shard, accounts in self.accounts.items()
        }

        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=4)
        self.logger.info(f"Account information saved to {output_file}")

    def _get_account_balance(self, address: str) -> str:
        retries = self.config.network.balance_query_retries
        for attempt in range(retries):
            try:
                account = self.provider.get_account(Address.new_from_bech32(address))
                return f"{float(account.balance) / 10**18:.4f}"
            except Exception as e:
                if attempt == retries - 1:
                    self.logger.error(f"Failed to query balance for {address}: {str(e)}")
                    raise BalanceQueryError(f"Failed to query balance for {address}: {str(e)}")
                time.sleep(self.config.network.balance_query_delay)

    def _log_account_generation(self, account: Account):
        self.logger.info(f"Generated account in Shard {account.shard} - Address: {account.address}")

    def _log_funding(self, account: Account, tx_hash: str):
        self.logger.info(f"Funding {account.address} - Transaction #: {tx_hash}")

if __name__ == "__main__":
    network_config = NetworkConfig(
        proxy_url=PROXY_URL,
        chain_id=CHAIN_ID,
        num_shards=NUM_SHARDS
    )

    wallet_config = WalletConfig(
        output_dir=OUTPUT_DIR,
        num_accounts_per_shard=NUM_ACCOUNTS_PER_SHARD,
        password=WALLET_PASSWORD,
        network=network_config
    )

    orchestrator = ShardWalletOrchestrator(
        config=wallet_config,
        funding_pem_path=FUNDING_WALLET_PEM
    )

    orchestrator.generate_accounts()
    orchestrator.fund_accounts()
    time.sleep(orchestrator.config.network.post_funding_wait)
    orchestrator.update_balances()
    orchestrator.save_accounts_info()

    # Prepare completion message values
    EGLD_DENOMINATOR = 10**18
    network = "devnet" if CHAIN_ID == "D" else "testnet"
    funded_amount = float(FUNDING_AMOUNT) / EGLD_DENOMINATOR

    # Completion message
    orchestrator.logger.info(
    f"Execution complete. Created a total of {NUM_ACCOUNTS_PER_SHARD * NUM_SHARDS} addresses (3 per shard) "
    f"on {network} and funded them with {funded_amount} xEGLD each using {FUNDING_WALLET_PEM}"
)
