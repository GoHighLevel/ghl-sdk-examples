# GHL SDK - OAuth Sample App

This sample application demonstrates how to use the GoHighLevel SDK with OAuth authentication for application which is Sub-Account only and can be installed by Agency & Sub-Account.

## Overview

This is a Node.js/Express application that shows how to:
- Implement OAuth 2.0 flow with GoHighLevel
- Handle OAuth callbacks and token management
- Use OAuth tokens to access the GHL API
- Display token information and make authenticated API calls

## Features

- **OAuth Flow**: Complete OAuth 2.0 implementation with authorization and callback handling
- **Token Management**: Displays access tokens, refresh tokens, and associated metadata
- **Contact Integration**: Fetch and display contact information using OAuth tokens

## Prerequisites

- Node.js (version 18 or higher)
- A GoHighLevel developer account
- An OAuth application registered in GoHighLevel
- Valid OAuth credentials (Client ID, Client Secret)

## Installation

1. **Clone or navigate to this directory**
   ```bash
   cd node/sample-app-oauth
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   CLIENT_ID=your_oauth_client_id
   CLIENT_SECRET=your_oauth_client_secret
   PORT=3000
   ```

   Replace the values with your actual OAuth application credentials from GoHighLevel.

4. **Configure OAuth Application**
   
   In your GoHighLevel OAuth app settings, make sure to set the redirect URI to:
   ```
   http://localhost:${PORT}/oauth-callback
   ```

## Running the Application

1. **Start the server**
   ```bash
   npm start
   ```

2. **Open your browser**
   
   Navigate to `http://localhost:3000`

3. **Complete OAuth Flow**
   - Click "Install Application" to start OAuth flow
   - You'll be redirected to GoHighLevel for authorization
   - After approval, you'll return to the token page
   - Click "Show Contact" to test API access

### Token Management
- Displays access token, refresh token, user type, company ID, and location ID
- Tokens are used for subsequent API calls
- Location ID is passed as resourceId for location-specific operations

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CLIENT_ID` | OAuth application client ID | Yes |
| `CLIENT_SECRET` | OAuth application client secret | Yes |
| `PORT` | Port number for the server (default: 3001) | No |

## OAuth Scopes

Make sure your OAuth application has the necessary scopes:
- `contacts.readonly` - To read contact information
- Additional scopes as needed for your use case

## Support

If you encounter any issues or have questions about OAuth integration, please refer to the main documentation or create an issue in the repository. 