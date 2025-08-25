require('dotenv').config();
const express = require('express');
const _ = require('lodash');
const { HighLevel, LogLevel, MongoDBSessionStorage } = require('@gohighlevel/api-client'); 
const bodyParser = require('body-parser');

const PORT = process.env.PORT || 3004;
const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;
const WEBHOOK_PUBLIC_KEY = process.env.WEBHOOK_PUBLIC_KEY;

const ghl = new HighLevel({
  clientId: CLIENT_ID,
  clientSecret: CLIENT_SECRET,
  logLevel: LogLevel.ERROR,
  sessionStorage: new MongoDBSessionStorage(process.env.MONGO_URL, 'local', 'tokens')
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

    if (
      _.isNil(WEBHOOK_PUBLIC_KEY) ||
      _.isEmpty(WEBHOOK_PUBLIC_KEY)
    )
      return res.redirect(
        '/error-page?msg=Please set WEBHOOK_PUBLIC_KEY env variable to proceed'
      );

  next();
};


app.use(checkEnv);
app.use(bodyParser.json());
app.use('/api/ghl/webhook', ghl.webhooks.subscribe());

app.get('/', (req, res) => {
  res.render('index');
});

app.get('/install', (req, res) => {
  const redirectUrl = ghl.oauth.getAuthorizationUrl(
    CLIENT_ID,
    `http://localhost:${PORT}/oauth-callback`,
    'contacts.readonly contacts.write locations.readonly'
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
    const resourceId = accessToken?.locationId ?? accessToken?.companyId;
    ghl.getSessionStorage().setSession(resourceId, accessToken);
    res.render('token', {
      token: accessToken,
      resourceId: resourceId,
      resourceType: accessToken?.userType
    });
  } catch (err) {
    console.error('Error fetching token:', err);
    res.redirect('/error-page?msg=Error fetching token');
  }
});

app.get('/contact', async (req, res) => {
  try {
    // get all tokens for the application
    const allTokens = await ghl.getSessionStorage().getSessionsByApplication()
    if (!allTokens?.length) {
      return res.redirect('/error-page?msg=Please authorize the application to proceed');
    }
    // get the location token (if you have bulk installed the app, then all tokens will be stored in the database)
    const locationToken = allTokens.find(token => token.userType?.toLowerCase() === 'location')
    if (!locationToken) {
      return res.redirect('/error-page?msg=Please authorize the application to proceed');
    }
    const locationId = locationToken.locationId
    const location = await ghl.locations.getLocation(
      {
        locationId
      },
      {
        preferredTokenType: 'location'
      }
    )
    if (!location?.location) {
      return res.redirect('/error-page?msg=No location found');
    }
    console.log('Location here:', location.location);
    const contacts = await ghl.contacts.getContacts(
      {
        locationId,
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
          locationId // need to pass locationId here so that SDK can fetch the token for the location (as it is not part of body or query parameter)
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


app.post('/api/ghl/webhook', (req, res) => {
  console.log('signature verified', req.isSignatureValid)
  return res.status(200).json({ status: 'success' });
});

app.use('/error-page', (req, res) => {
  res.render('error', {
    error: req.query.msg,
  });
});

app.listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
