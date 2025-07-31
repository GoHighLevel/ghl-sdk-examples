const { HighLevel } = require('@ghl/api-client');
const express = require('express');
const bodyParser = require('body-parser');
const _ = require('lodash');

const ghl = new HighLevel()

let tokenStore = {
  agencyToken: {},
  locationToken: {},
};

require('dotenv').config();
const PORT = process.env.PORT || 3000;
const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;
const SCOPES = 'contacts.readonly contacts.write';
const REDIRECT_URI_1 = `http://localhost:${PORT}/oauth-callback-agency`;
const REDIRECT_URI_2 = `http://localhost:${PORT}/oauth-callback-location`;
const GRANT_TYPES = {
  AUTHORIZATION_CODE: 'authorization_code',
  REFRESH_TOKEN: 'refresh_token',
};
const COMPANY_ID = process.env.COMPANY_ID;
const LOCATION_ID = process.env.LOCATION_ID;
const CONTACT_ID = process.env.CONTACT_ID;

const app = express();

// Set up Pug as view engine
app.set('view engine', 'pug');
app.set('views', './views');

app.use(
  bodyParser.urlencoded({
    limit: '50mb',
    extended: true,
  })
);

app.use(
  bodyParser.json({
    limit: '50mb',
    extended: true,
  })
);

const checkEnv = (req, res, next) => {
  if (_.isNil(CLIENT_ID))
    return res.redirect(
      '/error?msg=Please set HUBSPOT_CLIENT_ID env variable to proceed'
    );
  if (_.isNil(CLIENT_SECRET))
    return res.redirect(
      '/error?msg=Please set HUBSPOT_CLIENT_SECRET env variable to proceed'
    );

  next();
};

app.use(checkEnv);

const isAuthorized = () => {
  return (
    !_.isEmpty(tokenStore.agencyToken) || !_.isEmpty(tokenStore.locationToken)
  );
};

app.get('/', async (req, res) => {
  try {
    if (!isAuthorized()) {
      return res.render('index');
    }

    let contactResponse = null;
    if (Object.keys(tokenStore.locationToken).length) {
      console.log('calling get contacts api with location token');
      contactResponse = await ghl.contacts.getContact({
        contactId: CONTACT_ID,
      });
    }

    let allLocations = null;
    
    if (Object.keys(tokenStore.agencyToken).length && Object.keys(tokenStore.locationToken).length) {
      try {
        // when agency and location both token are available, you can choose which token to use while making api call
        const location = await ghl.locations.getLocation(
          {
            locationId: LOCATION_ID,
          },
          { preferredTokenType: 'agency' } // using agency token to fetch location details
        );
        console.log('Locations', location);
        
        // Pass all locations to the template
        if (location) {
          allLocations = location.location;
          console.log('All locations:', allLocations);
        }
      } catch (locationError) {
        console.log('Error fetching location info:', locationError);
      }
    }

    console.log('Response from API', contactResponse);

    // Render the contact information using Pug template
    res.render('contact', {
      contact: contactResponse?.contact,
      tokens: tokenStore,
      allLocations: allLocations,
    });
  } catch (e) {
    console.log('Error while fetching the contact', e);
    res.render('contact', {
      contact: null,
      error: 'Failed to fetch contact information',
      tokens: tokenStore,
      allLocations: null,
    });
  }
});

app.use('/oauth/location', async (req, res) => {
  console.log('Fetching authorization redirect url::');

  const authorizationUrl = ghl.oauth.getAuthorizationUrl(
    CLIENT_ID,
    REDIRECT_URI_2,
    SCOPES
  );
  console.log('Authorization Url', authorizationUrl);

  res.redirect(authorizationUrl);
});

app.use('/oauth/agency', async (req, res) => {
  console.log('Fetching authorization redirect url::');

  const authorizationUrl = ghl.oauth.getAuthorizationUrl(
    CLIENT_ID,
    REDIRECT_URI_1,
    SCOPES
  );
  console.log('Authorization Url', authorizationUrl);

  res.redirect(authorizationUrl);
});

app.use('/oauth-callback-location', async (req, res) => {
  const code = _.get(req, 'query.code');
  console.log('Code received from GHL:::', code);

  const getLocationToken = await ghl.oauth.getAccessToken({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    grant_type: GRANT_TYPES.AUTHORIZATION_CODE,
    code: code,
    redirect_uri: REDIRECT_URI_2,
  });
  console.log('Retrieving location access token result:', getLocationToken);

  tokenStore['locationToken'] = getLocationToken;
  ghl.setLocationAccessToken(getLocationToken.access_token);
  ghl.setLocationRefreshToken(getLocationToken.refresh_token);

  res.redirect('/');
});

app.use('/oauth-callback-agency', async (req, res) => {
  const code = _.get(req, 'query.code');
  console.log('Code received from GHL:::', code);

  const accessToken = await ghl.oauth.getAccessToken({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    grant_type: GRANT_TYPES.AUTHORIZATION_CODE,
    code: code,
    redirect_uri: REDIRECT_URI_1,
  });
  console.log('Retrieving agency access token result:', accessToken);

  if (accessToken.userType?.toLowerCase() === 'agency') {
    tokenStore['agencyToken'] = accessToken;
    ghl.setAgencyAccessToken(accessToken.access_token);
    ghl.setAgencyRefreshToken(accessToken.refresh_token);
  } else if (accessToken.userType?.toLowerCase() === 'location') {
    tokenStore['locationToken'] = accessToken;
    ghl.setLocationAccessToken(accessToken.access_token);
    ghl.setLocationRefreshToken(accessToken.refresh_token);
  }

  res.redirect('/');
});

app.use('/refresh-token', async (req, res) => {
  try {
    const agencyRefreshToken = ghl.getAgencyRefreshToken();
    const locationRefreshToken = ghl.getLocationRefreshToken();

    if (agencyRefreshToken) {
      console.log('Refreshing agency token...');
      const agencyToken = await ghl.oauth.refreshToken(agencyRefreshToken, CLIENT_ID, CLIENT_SECRET, GRANT_TYPES.REFRESH_TOKEN, 'Company');
      tokenStore.agencyToken = agencyToken;
      ghl.setAgencyAccessToken(agencyToken.access_token);
      ghl.setAgencyRefreshToken(agencyToken.refresh_token);
      console.log('Agency token refreshed successfully');
    }

    if (locationRefreshToken) {
      console.log('Refreshing location token...');
      const locationToken = await ghl.oauth.refreshToken(locationRefreshToken, CLIENT_ID, CLIENT_SECRET, GRANT_TYPES.REFRESH_TOKEN, 'Location');
      tokenStore.locationToken = locationToken;
      ghl.setLocationAccessToken(locationToken.access_token);
      ghl.setLocationRefreshToken(locationToken.refresh_token);
      console.log('Location token refreshed successfully');
    }
    
    // Render the refresh token page with updated tokens
    res.render('refreshToken', {
      tokens: tokenStore
    });
  } catch (error) {
    console.error('Error refreshing tokens:', error);
    res.render('refreshToken', {
      tokens: tokenStore,
      error: 'Failed to refresh tokens: ' + error.message
    });
  }
});

app.use('/pit', async (req, res) => {
  const privateIntegrationToken = process.env.PRIVATE_INTEGRATION_TOKEN;
  if (!privateIntegrationToken) {
    return res.redirect('/')
  }
  ghl.setPrivateIntegrationToken(privateIntegrationToken);
  try {
    const contact = await ghl.contacts.getContact({
      contactId: CONTACT_ID,
    });
    console.log('Contact', contact);
      res.render('contact', {
        contact: contact?.contact
      });
  } catch (error) {
    console.error('Error fetching contact:', error);
    res.redirect('/')
  }
});

app.listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
