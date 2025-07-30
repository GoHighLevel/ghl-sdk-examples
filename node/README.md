# GHL SDK Example with getContact Implementation

This project demonstrates how to use the GHL (GoHighLevel) SDK as a dependency and implements a `getContact` method for retrieving individual contacts.

## Installation

The project uses the local GHL SDK as a dependency. Make sure you have the GHL SDK available at the specified path.

```bash
npm install
```

## Usage

### JavaScript (Node.js)

```javascript
const { GHLSDKExample } = require('./index.js');

// Initialize with your access token
const accessToken = 'your-ghl-access-token';
const sdk = new GHLSDKExample(accessToken);

// Get a contact by ID
async function getContact() {
  try {
    const contactId = 'contact-id-here';
    const contact = await sdk.getContact(contactId);
    console.log('Contact:', contact);
  } catch (error) {
    console.error('Error:', error);
  }
}

// Get a contact with location ID (recommended)
async function getContactWithLocation() {
  try {
    const contactId = 'contact-id-here';
    const locationId = 'location-id-here';
    const contact = await sdk.getContactWithLocation(contactId, locationId);
    console.log('Contact:', contact);
  } catch (error) {
    console.error('Error:', error);
  }
}
```

### TypeScript

```typescript
import { GHLSDKExample } from './index';

// Initialize with your access token
const accessToken = 'your-ghl-access-token';
const sdk = new GHLSDKExample(accessToken);

// Get a contact by ID
async function getContact(): Promise<void> {
  try {
    const contactId = 'contact-id-here';
    const contact = await sdk.getContact(contactId);
    console.log('Contact:', contact);
  } catch (error) {
    console.error('Error:', error);
  }
}
```

## Available Methods

### `getContact(contactId: string)`

Retrieves a single contact by their contact ID using a direct API call.

**Parameters:**
- `contactId` (string): The unique identifier of the contact

**Returns:** Promise that resolves to the contact data

### `getContactWithLocation(contactId: string, locationId: string)`

Retrieves a single contact by their contact ID and location ID using the search API. This method is more robust as it uses the existing search functionality.

**Parameters:**
- `contactId` (string): The unique identifier of the contact
- `locationId` (string): The location ID where the contact belongs

**Returns:** Promise that resolves to the contact data

## Environment Variables

You can set your GHL access token as an environment variable:

```bash
export GHL_ACCESS_TOKEN=your-actual-access-token
```

## Running the Example

### JavaScript
```bash
npm start
# or
node index.js
```

### TypeScript
```bash
npm run build
node dist/index.js
```

## Development

### Build TypeScript
```bash
npm run build
```

### Watch Mode (Node.js 18+)
```bash
npm run dev
```

## Project Structure

```
├── package.json          # Project configuration and dependencies
├── tsconfig.json         # TypeScript configuration
├── index.js             # JavaScript implementation
├── index.ts             # TypeScript implementation
└── README.md            # This file
```

## Implementation Notes

The `getContact` method is implemented in two ways:

1. **Direct API Call**: Makes a direct GET request to `/contacts/{contactId}` endpoint
2. **Search-based**: Uses the existing `searchContactsAdvanced` method and filters results by contact ID

The search-based approach is recommended as it leverages the existing SDK functionality and is more likely to work with the current API structure.

## Dependencies

- `@ghl/api-client`: Local GHL SDK (file dependency)
- `axios`: HTTP client for API requests
- `typescript`: TypeScript compiler (dev dependency)
- `@types/node`: Node.js type definitions (dev dependency)

## License

MIT 