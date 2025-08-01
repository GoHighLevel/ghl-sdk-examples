# GHL SDK - Private Integration Token (PIT) Sample App

This sample application demonstrates how to use the GoHighLevel SDK with a Private Integration Token (PIT) for server-to-server authentication.

## Overview

This is a simple Node.js/Express application that shows how to:
- Configure the GHL SDK with a Private Integration Token
- Fetch contact information using the `getContact` method
- Display contact details in a web interface using Pug templates

## Features

- **PIT Authentication**: Uses Private Integration Token for secure API access
- **Contact Display**: Shows contact firstName, lastName, city, country, and locationId

## Prerequisites

- Node.js (version 18 or higher)
- A GoHighLevel account with API access
- A valid Private Integration Token

## Installation

1. **Clone or navigate to this directory**
   ```bash
   cd node/sample-app-pit
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   PRIVATE_INTEGRATION_TOKEN=your_private_integration_token_here
   PORT=3000
   ```

   Replace `your_private_integration_token_here` with your actual PIT token from GoHighLevel.

4. **Update Contact ID** (Optional)
   
   In `index.js`, update the `contactId` on line 41 with a valid contact ID from your GHL account:
   ```javascript
   const contactId = 'your_contact_id_here';
   ```

## Running the Application

1. **Start the server**
   ```bash
   npm start
   ```

2. **Open your browser**
   
   Navigate to `http://localhost:3000`

3. **Test the application**
   - You'll see the welcome page
   - Click "Show Contact" to fetch and display contact information

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PRIVATE_INTEGRATION_TOKEN` | Your GHL Private Integration Token | Yes |
| `PORT` | Port number for the server (default: 3000) | No |

## Support

If you encounter any issues or have questions, please refer to the main documentation or create an issue in the repository. 