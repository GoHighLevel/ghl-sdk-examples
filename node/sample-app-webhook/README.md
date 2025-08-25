# GHL SDK - Webhook Sample

This sample demonstrates how to subscribe to webhooks using the GHL SDK. You can implement webhook endpoints to perform activities once webhook events are received.

## Overview

This implementation shows how to:
- Subscribe to GHL webhooks using the SDK's built-in webhook functionality
- Handle webhook events automatically
- Verify webhook signatures for security
- Process incoming webhook 

**NOTE**: Subscribe method will only handle INSTALL and UNINSTALL events. It will generate and store token for INSTALL, while it will delete token for UNINSTALL from the storage which is used by SDK.

## Prerequisites

- Node.js 18+
- GHL OAuth application credentials
- Webhook endpoint configured in GHL

## Installation

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Set environment variables**
   ```env
   CLIENT_ID=your_oauth_client_id
   CLIENT_SECRET=your_oauth_client_secret
   WEBHOOK_PUBLIC_KEY=ghl_webhook_public_key
   ```

## Usage

To enable the default webhook execution provided by the SDK, add these 2 lines to your Express app:

```javascript
const express = require('express');
const bodyParser = require('body-parser');
const { HighLevel } = require('@gohighlevel/api-client');

const app = express();
const ghl = new HighLevel({
  clientId: 'your-client-id',
  clientSecret: 'your-client-secret'
});

// Required lines for webhook functionality
app.use(bodyParser.json());
app.use('/api/ghl/webhook', ghl.webhooks.subscribe());

app.listen(3000, () => {
  console.log('Webhook server running on port 3000');
});
```

## Webhook Endpoint

Once configured, your webhook endpoint will be available at:
```
POST http://your-domain.com/api/ghl/webhook
```

## How it Works

It will first validate the webhook signature. Once done, for bulk installation event it will generate token for each location and store it in the storage which is used by SDK.

Once this is done, it will pass the data to below endpoint. In this endpoint, you can implement whatever you want. 
```javascript
app.post('/api/ghl/webhook', (req, res) => {
  console.log('signature verified', req.isSignatureValid)
});
```

You will get `isSignatureValid` flag as shown above which will tell you if the webhook signature is valid or not. 

You can use `ghl.webhooks.verifySignature()` and pass the data to validate the webhook signature.