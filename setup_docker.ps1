# Create Docker volumes for persistent storage
docker volume create mcp-evm-keys
docker volume create mcp-evm-src

# Build the Docker image
docker build -t evm-signer-mcp -f Dockerfile.evm-signer .

# Remove any existing container
docker rm -f mcp-evm-signer 2>$null

# Ensure the TypeScript code is built
Write-Host "Building TypeScript code..."
Push-Location ..\mcp-evm-signer-main
npm install
npm run build
Pop-Location

# Copy built code to volume
Write-Host "Copying built code to Docker volume..."
docker run --rm `
    -v mcp-evm-src:/app/src `
    -v ${PWD}/../mcp-evm-signer-main:/source `
    alpine sh -c "cp -r /source/. /app/src/"

Write-Host "Docker setup complete. You can now run the agent."
