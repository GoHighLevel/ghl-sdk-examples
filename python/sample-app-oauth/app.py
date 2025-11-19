import os
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
from highlevel import HighLevel
import traceback

# Create a dedicated thread and event loop for async operations
executor = ThreadPoolExecutor(max_workers=1)
event_loop = None
loop_lock = threading.Lock()

def get_or_create_event_loop():
    """Get or create a persistent event loop in a dedicated thread"""
    global event_loop
    if event_loop is None:
        def create_loop():
            global event_loop
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)
            event_loop.run_forever()

        thread = threading.Thread(target=create_loop, daemon=True)
        thread.start()
        # Give the thread time to create the loop
        import time
        time.sleep(0.1)
    return event_loop

def run_async_in_loop(coro):
    """Run async coroutine in the persistent event loop"""
    loop = get_or_create_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()

# Load environment variables
load_dotenv()

PORT = int(os.getenv('PORT', 3003))
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')

# Initialize HighLevel SDK
ghl = HighLevel(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    log_level='debug'
)

app = Flask(__name__)

def check_env():
    """Middleware to check environment variables"""
    if request.path.startswith('/error-page'):
        return None

    if not CLIENT_ID or not CLIENT_ID.strip():
        return redirect(url_for('error_page', msg='Please set CLIENT_ID env variable to proceed'))

    if not CLIENT_SECRET or not CLIENT_SECRET.strip():
        return redirect(url_for('error_page', msg='Please set CLIENT_SECRET env variable to proceed'))

    return None

async def is_authorized(resource_id):
    """Check if the resource is authorized"""
    session_data = await ghl.get_session_storage().get_session(resource_id)
    return session_data is not None

@app.before_request
def before_request():
    """Apply environment check middleware"""
    result = check_env()
    if result:
        return result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/install')
def install():
    redirect_uri = f"http://localhost:{PORT}/oauth-callback"
    authorization_url = ghl.oauth.get_authorization_url(
        CLIENT_ID,
        redirect_uri,
        'contacts.readonly contacts.write'
    )
    print('Redirect URL:', authorization_url)
    return redirect(authorization_url)

@app.route('/oauth-callback')
def oauth_callback():
    """Handle OAuth callback - run async operation in event loop"""
    code = request.args.get('code')
    if not code:
        return redirect(url_for('error_page', msg='No code provided'))

    async def async_oauth_operations():
        access_token_data = await ghl.oauth.get_access_token({
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
        })
        print('Token:', access_token_data)

        await ghl.get_session_storage().set_session(access_token_data['locationId'], access_token_data)
        return access_token_data

    try:
        access_token_data = run_async_in_loop(async_oauth_operations())
        return render_template('token.html', token=access_token_data, location_id=access_token_data['locationId'])
    except Exception as err:
        print('Error fetching token:', err)
        traceback.print_exc()
        return redirect(url_for('error_page', msg=f'Error fetching token: {str(err)}'))

@app.route('/contact')
def contact():
    """Handle contact retrieval - run async operation in event loop"""
    try:
        resource_id = request.args.get('resourceId')
        if not resource_id:
            return redirect(url_for('error_page', msg='No resourceId provided'))

        # Run async operation without creating new event loop to avoid httpx connection issues
        async def async_contact_operations():
            # Check authorization
            authorized = await is_authorized(resource_id)
            if not authorized:
                return {'error': 'Please authorize the application to proceed'}

            contacts_data = await ghl.contacts.get_contacts(resource_id, None, None, None, 5)
            print('Fetched contacts:', contacts_data['contacts'])

            contact_id = contacts_data['contacts'][0]['id']
            if not contact_id:
                return {'error': 'No contact found'}

            contact_data = await ghl.contacts.get_contact(contact_id, { 'headers': { 'locationId': resource_id } })

            update_data = {
                'firstName': 'Tony updated'
            }

            await ghl.contacts.update_contact(
                contact_id,
                request_body=update_data,
                options={'headers': {'locationId': resource_id}}
            )
            return {'contact': contact_data['contact']}

        result = run_async_in_loop(async_contact_operations())

        if 'error' in result:
            return redirect(url_for('error_page', msg=result['error']))

        return render_template('contact.html', contact=result['contact'])

    except Exception as error:
        print('Error fetching contact:', error)
        traceback.print_exc()
        return redirect(url_for('index'))

@app.route('/refresh-token')
def refresh_token():
    """Handle token refresh - run async operation in event loop"""
    try:
        resource_id = request.args.get('resourceId')
        if not resource_id:
            return redirect(url_for('error_page', msg='No resourceId provided'))

        async def async_refresh_operations():
            token_details = await ghl.get_session_storage().get_session(resource_id)
            if not token_details:
                return {'error': 'No token found'}

            refreshed_token = await ghl.oauth.refresh_token(
                token_details['refresh_token'],
                CLIENT_ID,
                CLIENT_SECRET,
                'refresh_token',
                token_details.get('user_type', 'Location')
            )
            await ghl.get_session_storage().set_session(resource_id, refreshed_token)
            return refreshed_token

        result = run_async_in_loop(async_refresh_operations())

        if isinstance(result, dict) and 'error' in result:
            return redirect(url_for('error_page', msg=result['error']))

        return render_template('token.html', token=result, location_id=resource_id)

    except Exception as error:
        print('Error refreshing token:', error)
        traceback.print_exc()
        return redirect(url_for('error_page', msg='Error refreshing token'))

@app.route('/error-page')
def error_page():
    error_msg = request.args.get('msg', 'Unknown error')
    return render_template('error.html', error=error_msg)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
