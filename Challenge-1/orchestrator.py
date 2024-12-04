import json
import logging
import time
from pathlib import Path
from typing import Dict, List

from multiversx_sdk import (
    Address, Mnemonic, UserWallet, UserPEM, AddressComputer,
    ProxyNetworkProvider, Transaction, AccountNonceHolder,
    TransactionComputer, UserSigner
)
from config import (
    NetworkConfig, WalletConfig, WalletGenerationError,
    FundingError, BalanceQueryError, TEMP_WALLET_FILE,
    ACCOUNTS_INFO_FILE
)
from models import Account
from logger import setup_logging

class FundingWalletManager:
    """Class to manage funding of accounts"""
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
    """Class to generate wallets"""
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

class ShardWalletOrchestrator:
    """Class to orchestrate wallet generation, funding, and balance updates"""
    def __init__(self, config: WalletConfig, funding_pem_path: Path):
        self.config = config
        self.provider = ProxyNetworkProvider(config.network.proxy_url)
        self.logger = setup_logging(config.output_dir)
        self.wallet_generator = WalletGenerator(config, self.logger)
        self.funding_manager = FundingWalletManager(config.network, funding_pem_path, self.logger)
        self.accounts: Dict[int, List[Account]] = {i: [] for i in range(config.network.num_shards)}

    def generate_accounts(self):
        """
        Generates accounts distributed across shards more efficiently by:
        1. Tracking needed accounts per shard
        2. Using all valid generated accounts
        3. Only generating until requirements are met
        4. Cleaning up unused accounts
        """
        # Track how many accounts we still need for each shard
        needed_per_shard = {
            shard: self.config.num_accounts_per_shard
            for shard in range(self.config.network.num_shards)
        }

        # Keep generating until we have enough accounts for all shards
        while any(needed > 0 for needed in needed_per_shard.values()):
            account = self.wallet_generator.generate_account()
            shard = account.shard

            # If we still need accounts for this shard, keep it
            if needed_per_shard[shard] > 0:
                self.accounts[shard].append(account)
                needed_per_shard[shard] -= 1
                self._log_account_generation(account)

                # Log progress when each shard is completed
                if needed_per_shard[shard] == 0:
                    self.logger.info(f"Completed account generation for shard {shard}")
            else:
                # Clean up files for unused account
                try:
                    if Path(account.wallet_file).exists():
                        Path(account.wallet_file).unlink()
                    if Path(account.pem_file).exists():
                        Path(account.pem_file).unlink()
                    self.logger.debug(f"Cleaned up unused account files for shard {shard}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up unused account files: {str(e)}")

        # Log final statistics
        total_accounts = sum(len(accounts) for accounts in self.accounts.values())
        discarded = len([p for p in self.config.output_dir.glob("wallet_*")] +
                    [p for p in self.config.output_dir.glob("*.pem")]) - total_accounts
        self.logger.info(
            f"Account generation complete. Created {total_accounts} accounts "
            f"across {self.config.network.num_shards} shards. "
            f"Discarded {discarded} accounts that didn't match needed shards."
        )

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
