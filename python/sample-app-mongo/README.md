# GHL SDK - Python Mongo Sample App

This sample application demonstrates how to use the GoHighLevel Python SDK with OAuth authentication and use MongoDb as storage options for token management. 

## Overview

This is a Python/Flask application that shows how to:
- Implement OAuth 2.0 flow with GoHighLevel
- Handle OAuth callbacks and token management
- Use OAuth tokens to access the GHL API
- Display token information and make authenticated API calls

## Installation

1. **Navigate to this directory**
   ```bash
   cd python/sample-app-mongo
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