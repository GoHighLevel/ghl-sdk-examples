# GHL SDK - MongoDB Storage Sample

This sample demonstrates using MongoDB as a storage backend for GHL SDK session and token management. MongoDB storage support is provided by default in the SDK.

## Overview

Instead of using the default in-memory storage, this implementation uses MongoDB to persist OAuth tokens and session data. This enables:
- Token persistence across application restarts
- Shared token storage in multi-instance deployments
- Automatic token refresh and database updates

## Prerequisites

- Node.js 18+
- MongoDB server running
- GHL OAuth application credentials

## Installation

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Start MongoDB** (if not already running)
   ```bash
   mongod
   ```

3. **Set environment variables**
   ```env
   CLIENT_ID=your_oauth_client_id
   CLIENT_SECRET=your_oauth_client_secret
   MONGODB_URI=mongodb://localhost:27017/ghl-sessions
   ```

## Usage

```javascript
const { HighLevel, MongoSessionStorage } = require('@gohighlevel/api-client');

// Initialize MongoDB storage
const mongoStorage = new MongoSessionStorage({
  uri: 'mongodb://localhost:27017/ghl-sessions',
  collection: 'sessions'
});

// Initialize GHL SDK with MongoDB storage
const ghl = new HighLevel({
  clientId: 'your-client-id',
  clientSecret: 'your-client-secret',
  sessionStorage: mongoStorage
});

// Use normally - tokens will be stored in MongoDB
const contact = await ghl.contacts.getContact({
  contactId: 'contact-id',
  resourceId: 'location-id'
});
```

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `uri` | mongodb://localhost:27017 | MongoDB connection URI |
| `collection` | sessions | Collection name for sessions |

## How it Works

1. **Session Storage**: OAuth tokens are stored in MongoDB collections
2. **Token Retrieval**: SDK automatically retrieves tokens from MongoDB when making API calls
3. **Persistence**: Tokens survive application restarts and can be shared across instances
4. **Auto Refresh**: If the token is expired, it will be auto refreshed and new token will be updated in the database
