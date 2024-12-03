import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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

class WalletGenerationError(Exception):
    """Base exception for wallet generation errors"""
    pass

class FundingError(Exception):
    """Exception for funding-related errors"""
    pass

class BalanceQueryError(Exception):
    """Exception for balance query errors"""
    pass
