require('dotenv').config();
const express = require('express');
const _ = require('lodash');
const { HighLevel } = require('@gohighlevel/api-client');

const PORT = process.env.PORT || 3001;
const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;

const ghl = new HighLevel({
  clientId: CLIENT_ID,
  clientSecret: CLIENT_SECRET,
});

const app = express();

// Set up Pug as view engine
app.set('view engine', 'pug');
app.set('views', './views');

const checkEnv = (req, res, next) => {
  if (_.startsWith(req.url, '/error-page')) return next();

  if (
    _.isNil(CLIENT_ID) ||
    _.isEmpty(CLIENT_ID)
  )
    return res.redirect(
      '/error-page?msg=Please set CLIENT_ID env variable to proceed'
    );

  if (
    _.isNil(CLIENT_SECRET) ||
    _.isEmpty(CLIENT_SECRET)
  )
    return res.redirect(
      '/error-page?msg=Please set CLIENT_SECRET env variable to proceed'
    );

  next();
};
const isAuthorized = async (resourceId) => {
  return !_.isEmpty(await ghl.getSessionStorage().getSession(resourceId));
};

app.use(checkEnv);

app.get('/', (req, res) => {
  res.render('index');
});

app.get('/install', (req, res) => {
  const redirectUrl = ghl.oauth.getAuthorizationUrl(
    CLIENT_ID,
    `http://localhost:${PORT}/oauth-callback`,
    'contacts.readonly contacts.write'
  );
  console.log('Redirect URL', redirectUrl);
  return res.redirect(redirectUrl);
});

app.get('/oauth-callback', async (req, res) => {
  const code = req.query.code;
  if (!code) {
    return res.redirect('/error-page?msg=No code provided');
  }
  try {
    const accessToken = await ghl.oauth.getAccessToken({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      code,
      grant_type: 'authorization_code',
    });
    console.log('Token', accessToken);
    ghl.getSessionStorage().setSession(accessToken.locationId, accessToken);
    res.render('token', {
      token: accessToken,
      locationId: accessToken.locationId,
    });
  } catch (err) {
    console.error('Error fetching token:', err);
    res.redirect('/error-page?msg=Error fetching token');
  }
});

app.get('/contact', async (req, res) => {
  try {
    const resourceId = req.query.resourceId;
    if (!resourceId) {
      return res.redirect('/error-page?msg=No resourceId provided');
    }
    if (!await isAuthorized(resourceId)) {
      return res.redirect(
        '/error-page?msg=Please authorize the application to proceed'
      );
    }
    const contacts = await ghl.contacts.getContacts(
      {
        locationId: resourceId,
        limit: 5
      },
    );
    console.log('Fetched contacts:', contacts.contacts);
    const contactId = contacts.contacts[0].id;
    if (!contactId) {
      return res.redirect('/error-page?msg=No contact found');
    } 
    const contact = await ghl.contacts.getContact(
      {
        contactId
      },
      {
        headers: {
          locationId: resourceId // need to pass locationId here so that SDK can fetch the token for the location (as it is not part of body or query parameter)
        },
      }
    );
    console.log('Contact here:', contact.contact);
    return res.render('contact', {
      contact: contact?.contact,
    });
  } catch (error) {
    console.error('Error fetching contact:', error);
    res.redirect('/');
  }
});

app.get('/refresh-token', async (req, res) => {
  try {
    const resourceId = req.query.resourceId;
    if (!resourceId) {
      return res.redirect('/error-page?msg=No resourceId provided');
    }
    const tokenDetails = await ghl.getSessionStorage().getSession(resourceId);
    if (!tokenDetails) {
      return res.redirect('/error-page?msg=No token found');
    }
    const token = await ghl.oauth.refreshToken(
      tokenDetails.refresh_token,
      CLIENT_ID,
      CLIENT_SECRET,
      'refresh_token',
      tokenDetails.userType
    );
    ghl.getSessionStorage().setSession(resourceId, token);
    res.render('token', {
      token: token,
      locationId: resourceId,
    });
  } catch (error) {
    console.error('Error refreshing token:', error);
    res.redirect('/error-page?msg=Error refreshing token');
  }
});

app.use('/error-page', (req, res) => {
  res.render('error', {
    error: req.query.msg,
  });
});

app.listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
