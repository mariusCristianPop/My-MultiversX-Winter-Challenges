# Setting Up MultiversX Wallet Generator

## Prerequisites
- Python 3.8+
- Git

## Steps

### 1. Get the Code
```bash
git clone [repository-url]
cd [repository-name]
```

### 2. Set Up Python Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Required Packages
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
1. Copy `.env.example` to `.env`
   ```bash
   cp .env.example .env
   ```
2. Place your funded devnet wallet .pem file in project root as `funding_wallet.pem` OR use the already existing one as long as it has funds.

### 5. Run the Script
```bash
python main.py
```

### What Will Happen
- Creates 9 wallets (3 per shard)
- Funds each with 0.01 xEGLD
- Saves wallet info in `devnet_wallets/accounts_info.json`
- Creates log files in `devnet_wallets/`

### Important
- The `funding_wallet.pem` must have enough funds
- Generated wallets will be in `devnet_wallets/` directory
