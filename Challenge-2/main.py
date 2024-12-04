from multiversx_sdk import (
    Address,
    TokenTransfer,
    Transaction,
    ProxyNetworkProvider,
    AccountNonceHolder,
    UserSigner,
    TransactionComputer
)
from pathlib import Path
import json
import time

# Configuration
GATEWAY_URL = "https://devnet-gateway.multiversx.com"
CHAIN_ID = "D"
SYSTEM_SC_ADDRESS = "erd1qqqqqqqqqqqqqqqpqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzllls8a5w6u"
ISSUANCE_COST = 50_000_000_000_000_000  # 0.05 EGLD
GAS_LIMIT = 60_000_000

def create_token_issuance_transaction(
    sender: Address,
    nonce: int,
    token_name: str,
    token_ticker: str,
    initial_supply: int,
    num_decimals: int = 8,
    can_freeze: bool = True,
    can_wipe: bool = True,
    can_pause: bool = True,
    can_mint: bool = True,
    can_burn: bool = True,
    can_change_owner: bool = True,
    can_upgrade: bool = True,
    can_add_special_roles: bool = True
) -> Transaction:
    # Convert properties to hex-encoded strings
    properties = [
        ("canFreeze", str(can_freeze).lower()),
        ("canWipe", str(can_wipe).lower()),
        ("canPause", str(can_pause).lower()),
        ("canMint", str(can_mint).lower()),
        ("canBurn", str(can_burn).lower()),
        ("canChangeOwner", str(can_change_owner).lower()),
        ("canUpgrade", str(can_upgrade).lower()),
        ("canAddSpecialRoles", str(can_add_special_roles).lower())
    ]

    # Build data field
    data_parts = ["issue"]
    data_parts.append(token_name.encode().hex())
    data_parts.append(token_ticker.encode().hex())

    # Ensure supply has even number of hex chars
    supply_hex = hex(initial_supply)[2:]
    if len(supply_hex) % 2 != 0:
        supply_hex = "0" + supply_hex
    data_parts.append(supply_hex)

    # Ensure decimals has even number of hex chars
    decimals_hex = hex(num_decimals)[2:]
    if len(decimals_hex) % 2 != 0:
        decimals_hex = "0" + decimals_hex
    data_parts.append(decimals_hex)

    for prop_name, prop_value in properties:
        data_parts.append(prop_name.encode().hex())
        data_parts.append(prop_value.encode().hex())

    data = "@".join(data_parts)

    return Transaction(
        nonce=nonce,
        value=ISSUANCE_COST,
        sender=sender.to_bech32(),
        receiver=SYSTEM_SC_ADDRESS,
        gas_limit=GAS_LIMIT,
        chain_id=CHAIN_ID,
        data=data.encode()
    )

def check_devnet_wallets_directory(base_path: Path):
    """
    Check if the devnet_wallets directory exists and contains required files.
    Raises FileNotFoundError if directory or required files are missing.
    """
    if not base_path.exists():
        raise FileNotFoundError(
            f"Required directory '{base_path}' not found! "
            "Please ensure the devnet_wallets directory exists in the current working directory."
        )

    if not base_path.is_dir():
        raise NotADirectoryError(
            f"'{base_path}' exists but is not a directory! "
            "Please ensure devnet_wallets is a proper directory."
        )

    accounts_info_path = base_path / "accounts_info.json"
    if not accounts_info_path.exists():
        raise FileNotFoundError(
            f"Required file 'accounts_info.json' not found in {base_path}! "
            "Please ensure the accounts information file exists."
        )

def load_accounts_from_json(base_path: Path) -> list:
    """
    Load all account details from the accounts info JSON file

    Args:
        base_path: Path to the devnet_wallets directory

    Returns:
        list: List of dictionaries containing account addresses and PEM file paths

    Raises:
        FileNotFoundError: If directory or required files are missing
        json.JSONDecodeError: If accounts_info.json is invalid
    """
    # First check if directory exists and is properly structured
    check_devnet_wallets_directory(base_path)

    # Read the accounts_info.json from devnet_wallets directory
    json_path = base_path / "accounts_info.json"

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Failed to parse accounts_info.json: {str(e)}. "
            "Please ensure the file contains valid JSON data.",
            e.doc,
            e.pos
        )

    accounts = []
    for shard in ['shard_0', 'shard_1', 'shard_2']:
        for account in data[shard]:
            # Convert Windows-style paths to proper Path objects
            pem_file_path = base_path / account['pem_file'].replace('devnet_wallets\\', '')

            # Verify PEM file exists
            if not pem_file_path.exists():
                raise FileNotFoundError(
                    f"PEM file not found: {pem_file_path}\n"
                    "Please ensure all referenced PEM files exist in the devnet_wallets directory."
                )

            accounts.append({
                'address': account['address'],
                'pem_file': str(pem_file_path)
            })

    return accounts

def process_account_token_issuance(
    account_details: dict,
    provider: ProxyNetworkProvider,
    tx_computer: TransactionComputer
) -> list:
    """Process token issuance for a single account"""
    try:
        # Load account's PEM file
        signer = UserSigner.from_pem_file(Path(account_details['pem_file']))
        sender_address = signer.get_pubkey().to_address()
        print(f"\nProcessing account: {sender_address.to_bech32()}")

        # Get account nonce
        account = provider.get_account(sender_address)
        nonce_holder = AccountNonceHolder(account.nonce)

        transactions = []
        # Create three tokens for this account
        for i in range(3):
            token_name = f"WinterToken{sender_address.to_bech32()[-6:]}{i+1}"
            token_ticker = "WINTER"
            initial_supply = 100_000_000 * (10 ** 8)  # 100 million tokens with 8 decimals

            tx = create_token_issuance_transaction(
                sender=sender_address,
                nonce=nonce_holder.get_nonce_then_increment(),
                token_name=token_name,
                token_ticker=token_ticker,
                initial_supply=initial_supply
            )
            tx.signature = signer.sign(tx_computer.compute_bytes_for_signing(tx))
            transactions.append(tx)
            print(f"Prepared issuance of {token_name} ({token_ticker})")

        return transactions
    except Exception as e:
        print(f"Error processing account {account_details['address']}: {e}")
        return []

def main():
    # Initialize network provider and transaction computer
    provider = ProxyNetworkProvider(GATEWAY_URL)
    tx_computer = TransactionComputer()

 # Load accounts from JSON using the devnet_wallets directory
    base_path = Path("devnet_wallets")
    accounts = load_accounts_from_json(base_path)
    print(f"Loaded {len(accounts)} accounts from JSON file")

    total_transactions = []
    # Process each account
    for account_details in accounts:
        # Create transactions for this account
        account_transactions = process_account_token_issuance(
            account_details,
            provider,
            tx_computer
        )
        total_transactions.extend(account_transactions)

        # Send transactions in batches
        if account_transactions:
            print(f"\nSending {len(account_transactions)} transactions for account {account_details['address']}...")
            batch_size = 5
            for i in range(0, len(account_transactions), batch_size):
                batch = account_transactions[i:i + batch_size]
                print(f"\nSending batch {i//batch_size + 1}:")
                for tx in batch:
                    print(f"\nTransaction details:")
                    print(f"Sender: {tx.sender}")
                    print(f"Value: {tx.value}")
                    print(f"Data: {tx.data.decode()}")
                    print(f"Nonce: {tx.nonce}")

                tx_hashes = provider.send_transactions(batch)
                print(f"Batch sent. Waiting for processing...")
                time.sleep(6)  # Wait between batches

            print("\nWaiting for final processing...")
            time.sleep(20)

    # Print summary
    print("\nToken issuance complete!")
    print(f"Total tokens issued: {len(total_transactions)}")
    print(f"Accounts processed: {len(accounts)}")
    print(f"Tokens per account: 3")

if __name__ == "__main__":
    main()
