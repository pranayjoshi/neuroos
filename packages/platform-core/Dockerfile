# NeuroOS Platform Core — Job 04
# Implemented by the Platform Architect agent. This is a stub.
FROM node:20-slim

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@9 --activate

# Copy workspace manifests for dependency installation
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
COPY jobs/00_shared_contracts/package.json ./jobs/00_shared_contracts/
COPY packages/platform-core/package.json ./packages/platform-core/

RUN pnpm install --frozen-lockfile --filter @neuroos/platform-core...

# Copy source
COPY jobs/00_shared_contracts/ ./jobs/00_shared_contracts/
COPY packages/platform-core/ ./packages/platform-core/

WORKDIR /app/packages/platform-core

EXPOSE 3000

CMD ["node", "dist/api/server.js"]
