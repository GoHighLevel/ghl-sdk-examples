require('dotenv').config();
const express = require('express');
const _ = require('lodash');
const { HighLevel } = require('@ghl/api-client');

const PORT = process.env.PORT || 3000;
const PRIVATE_INTEGRATION_TOKEN = process.env.PRIVATE_INTEGRATION_TOKEN;

const ghl = new HighLevel({
  privateIntegrationToken: PRIVATE_INTEGRATION_TOKEN,
});

const app = express();

// Set up Pug as view engine
app.set('view engine', 'pug');
app.set('views', './views');

const checkEnv = (req, res, next) => {
  if (_.startsWith(req.url, '/error-page')) return next();

  if (
    _.isNil(PRIVATE_INTEGRATION_TOKEN) ||
    _.isEmpty(PRIVATE_INTEGRATION_TOKEN)
  )
    return res.redirect(
      '/error-page?msg=Please set PRIVATE_INTEGRATION_TOKEN env variable to proceed'
    );

  next();
};

app.use(checkEnv);

app.get('/', (req, res) => {
  res.render('index');
});

app.get('/contact', async (req, res) => {
  try {
    const contactId = 'zBG0T99IsBgOoXUrcROH';
    const contact = await ghl.contacts.getContact({
      contactId,
    });
    console.log('Contact', contact);
    res.render('contact', {
      contact: contact?.contact,
    });
  } catch (error) {
    console.error('Error fetching contact:', error);
    res.redirect('/');
  }
});

app.use('/error-page', (req, res) => {
  res.render('error', {
    error: req.query.msg,
  });
});

app.listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
