# GHL SDK - Redis Storage Sample

This sample demonstrates using Redis as a storage backend for GHL SDK session and token management. You can implement your own storage class which should extend SessionStorage from `@highlevel/api-client`

## Overview

Instead of using the default in-memory storage or mongo db storage, this implementation uses Redis to persist OAuth tokens and session data. This enables:
- Token persistence across application restarts
- Shared token storage in multi-instance deployments
- Automatic token expiration with Redis TTL

## Prerequisites

- Node.js 18+
- Redis server running
- GHL OAuth application credentials

## Installation

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Start Redis** (if not already running)
   ```bash
   redis-server
   ```

3. **Set environment variables**
   ```env
   CLIENT_ID=your_oauth_client_id
   CLIENT_SECRET=your_oauth_client_secret
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

## Usage

```javascript
const { HighLevel } = require('@highlevel/api-client');
const RedisStorage = require('./storage/redis-storage');

// Initialize Redis storage
const redisStorage = new RedisStorage({
  host: 'localhost',
  port: 6379
});

// Initialize GHL SDK with Redis storage
const ghl = new HighLevel({
  clientId: 'your-client-id',
  clientSecret: 'your-client-secret',
  sessionStorage: redisStorage
});

// Use normally - tokens will be stored in Redis
const contact = await ghl.contacts.getContact({
  contactId: 'contact-id',
  resourceId: 'location-id'
});
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `host` | localhost | Redis host |
| `port` | 6379 | Redis port |
| `password` | - | Redis password |

## How it Works

1. **Session Storage**: OAuth tokens are stored in Redis with automatic expiration
2. **Token Retrieval**: SDK automatically retrieves tokens from Redis when making API calls
3. **Persistence**: Tokens survive application restarts and can be shared across instances
4. **Auto Refresh**: If the token is expired, it will be auto refreshed and new token will be updated in the db. 