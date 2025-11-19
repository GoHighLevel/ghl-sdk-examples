# GHL SDK - Python Webhook Sample App

This sample application demonstrates how to use the GoHighLevel Python SDK and use webhooks to manage `INSTALL` and `UNINSTALL` events. If you are using any storage to store tokens and use webhooks, based on the event it will automatically generate token for you and will store it. If the token is store, SDK will refresh it automatically. 

## Overview

This is a Python/Flask application that shows how to:
- Implement OAuth 2.0 flow with GoHighLevel
- Handle OAuth callbacks and token management using SQL
- Use OAuth tokens to access the GHL API
- Display token information and make authenticated API calls

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

   Create a `.env` file in the root directory and copy `.env.example` and add values.

## Running the Application

1. **Start the server**
   ```bash
   python app.py
   ```