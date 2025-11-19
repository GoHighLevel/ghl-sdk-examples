# GHL SDK - Python Webhook Sample App (Django)

This sample application demonstrates how to use the GoHighLevel Python SDK with Django and use webhooks to manage `INSTALL` and `UNINSTALL` events. If you are using any storage to store tokens and use webhooks, based on the event it will automatically generate token for you and will store it. If the token is stored, SDK will refresh it automatically.

## Overview

This is a Python/Django application that shows how to:
- Implement OAuth 2.0 flow with GoHighLevel
- Handle OAuth callbacks and token management using MongoDB
- Use OAuth tokens to access the GHL API
- Display token information and make authenticated API calls
- Handle webhooks for automatic token management

## Installation

1. **Navigate to this directory**
   ```bash
   cd python/sample-app-webhook
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   Create a `.env` file in the root directory and copy `.env.example` and add values:
   ```bash
   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   PORT=3003
   MONGO_URL=mongodb://localhost:27017
   MONGO_DB_NAME=local
   COLLECTION_NAME=tokens
   ```