# AI Agent of Profit (AoP) - Cryptocurrency Trading Platform

A sophisticated autonomous agent-based platform for cryptocurrency trading, wallet management, and DeFi operations.

![AI Agent of Profit](static/img/logo.png)

## Overview

AI Agent of Profit (AoP) is a cutting-edge DeFi trading agent that connects to EVM-compatible blockchains (Ethereum Virtual Machine) and provides an intuitive interface for managing digital assets.
## Architecture

The platform consists of several key components:

### Backend Components

1. **EVM Agent (evm_agent.py)**
   - Core component that connects to the EVM signer MCP server
   - Handles interactions with blockchain wallets and DeFi protocols
   - Implements an agent loop pattern: User Query → LLM Tool Selection → Tool Execution → LLM Summary → Response

2. **Flask Web Server (app.py)**
   - Serves the web interface
   - Handles API requests from the frontend
   - Manages communication with the EVM agent

3. **MCP (Machine Callable Programs) Integration**
   - Connects to blockchain networks via Docker containers
   - Provides secure signing capabilities for transactions
   - Tools for wallet management and DeFi protocol interactions

### Frontend Components

1. **Responsive Web Interface**
   - Modern UI with glass-morphism, gradients, and subtle animations
   - Hideable sidebar that works on both desktop and mobile devices
   - Dark theme with premium typography (DM Sans, Playfair Display, Fira Code)

2. **Interactive Chat Interface**
   - Natural language interaction with the AI agent
   - Display of tool calls and operations in a clean, compact format
   - Real-time feedback on blockchain operations

## Features

- **Wallet Management**: View balances, addresses, and transaction history
- **Trading Operations**: Execute trades across various DeFi protocols
- **Market Analysis**: Get current prices, historical data, and technical analysis
- **DeFi Integration**: Interact with lending protocols, liquidity pools, and more
- **Autonomous Agent**: AI-powered assistant that can understand natural language requests


## Installation Requirements

- Python 3.8+
- Docker
- OpenAI API key
- Alchemy API key (for blockchain node access)

## Setup Instructions

1. **Clone the repository**
   ```
   git clone https://github.com/yourusername/mcp-openai-crypto.git
   cd mcp-openai-crypto
   ```

2. **Create and configure environment variables**
   Create a `.env` file with the following:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ALCHEMY_API_KEY=your_alchemy_api_key
   LLM_MODEL=gpt-4
   ```

3. **Set up Docker for EVM signer**
   ```
   docker pull evm-signer-mcp
   ```

4. **Install Python dependencies**
   ```
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```
   python app.py
   ```

## Usage

1. Access the web interface at `http://localhost:5000`
2. Use the chat interface to communicate with the AI Agent of Profit
3. Request operations such as:
   - "Show my wallet balance"
   - "What's the current price of ETH?"
   - "Analyze the market trend for BTC"
   - "Execute a swap from ETH to USDT"

## Technical Details

### EVM Agent Flow

The EVM agent follows this execution pattern:
1. User submits a query through the interface
2. LLM processes the query and selects appropriate tools
3. Selected tools are executed against the blockchain
4. Results are processed by the LLM
5. A comprehensive response is generated for the user

### Current Configuration

- **Default Network**: Monad Testnet
- **Default Wallet**: 0x95723432b6a145b658995881b0576d1e16850b02
- **Model**: GPT-4 (configurable via environment variable)

### Supported Protocols

- **Curvance Protocol**
- (Additional protocols can be integrated)

## Development

To extend the platform, you can:

1. Add new DeFi protocol integrations
2. Enhance the UI with additional features
3. Implement more advanced trading strategies
4. Add support for more blockchain networks

## License

[Specify your license here]

## Acknowledgements

- OpenAI for the language model capabilities
- MCP framework for secure blockchain interactions
- Monad for testnet access
