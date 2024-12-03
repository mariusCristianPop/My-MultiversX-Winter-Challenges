import time
from config import (
   NetworkConfig, WalletConfig, NUM_SHARDS, OUTPUT_DIR,
   NUM_ACCOUNTS_PER_SHARD, WALLET_PASSWORD, FUNDING_WALLET_PEM,
   CHAIN_ID, PROXY_URL, FUNDING_AMOUNT
)
from orchestrator import ShardWalletOrchestrator


if __name__ == "__main__":
   # Initialize network configuration with proxy URL, chain ID and number of shards
   network_config = NetworkConfig(
       proxy_url=PROXY_URL,
       chain_id=CHAIN_ID,
       num_shards=NUM_SHARDS
   )

   # Configure wallet settings including output directory, accounts per shard and credentials
   wallet_config = WalletConfig(
       output_dir=OUTPUT_DIR,
       num_accounts_per_shard=NUM_ACCOUNTS_PER_SHARD,
       password=WALLET_PASSWORD,
       network=network_config
   )

   # Create orchestrator to manage wallet generation and funding
   orchestrator = ShardWalletOrchestrator(
       config=wallet_config,
       funding_pem_path=FUNDING_WALLET_PEM
   )

   orchestrator.generate_accounts()  # Generate wallets for each shard
   orchestrator.fund_accounts()      # Fund each wallet with EGLD
   time.sleep(orchestrator.config.network.post_funding_wait)  # Wait for transactions to complete
   orchestrator.update_balances()    # Update wallet balances after funding
   orchestrator.save_accounts_info() # Save wallet information to file

   # Calculate funded amount in EGLD for saving it to log
   EGLD_DENOMINATOR = 10**18  # EGLD has 18 decimal places
   network = "devnet" if CHAIN_ID == "D" else "testnet"  # Determine network from chain ID
   funded_amount = float(FUNDING_AMOUNT) / EGLD_DENOMINATOR  # Convert amount to EGLD

   # Log summary of wallets created and funded
   orchestrator.logger.info(
       f"Execution complete. Created a total of {NUM_ACCOUNTS_PER_SHARD * NUM_SHARDS} addresses (3 per shard) "
       f"on {network} and funded them with {funded_amount} xEGLD each using {FUNDING_WALLET_PEM}"
   )
