import os
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv
from highlevel import HighLevel
import traceback
import inspect

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
# Treat trailing-slash URLs (e.g. /install/) the same as /install.
app.url_map.strict_slashes = False

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
        ''
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
            'clientId': CLIENT_ID,
            'clientSecret': CLIENT_SECRET,
            'code': code,
            'grantType': 'authorization_code',
        })
        print('Token:', access_token_data)
        return access_token_data

    try:
        access_token_data = run_async_in_loop(async_oauth_operations())
        location_id = access_token_data.get('locationId')

        if location_id:
            # Location-level install: store under the location id and show the token.
            run_async_in_loop(
                ghl.get_session_storage().set_session(location_id, access_token_data)
            )
            return render_template('token.html', token=access_token_data, location_id=location_id)

        # Company (agency) level install: no location id yet. Store the company
        # token, then show a loading page that polls until a location token is ready.
        company_id = access_token_data.get('companyId')
        if not company_id:
            return redirect(url_for('error_page', msg='Token response had neither locationId nor companyId'))

        run_async_in_loop(
            ghl.get_session_storage().set_session(company_id, access_token_data)
        )
        # Make the agency (company) token available to the agency-scoped polling calls
        # (get_installed_location / get_location_access_token) directly via config —
        # get_token_for_security checks config before storage, so this avoids a
        # cross-request storage round-trip. Cleared once a location token resolves.
        ghl.update_config({
            'agency_access_token': access_token_data.get('accessToken') or access_token_data.get('access_token')
        })
        return render_template('loading.html', company_id=company_id)
    except Exception as err:
        print('Error fetching token:', err)
        traceback.print_exc()
        return redirect(url_for('error_page', msg=f'Error fetching token: {str(err)}'))

@app.route('/install-locations')
def install_locations():
    """Poll endpoint: resolve a location token from the company token (JSON)."""
    company_id = request.args.get('companyId')
    if not company_id:
        return jsonify({'ready': False, 'error': 'No companyId provided'})

    async def resolve_location():
        app_id = (CLIENT_ID or '').split('-')[0]
        installed = await ghl.oauth.get_installed_location(
            company_id=company_id,
            app_id=app_id,
            is_installed=True,
            options={'headers': {'companyId': company_id}}
        )
        items = installed.get('items', []) if isinstance(installed, dict) else []

        resolved_location_id = None
        for item in items:
            location_id = item.get('_id')
            if not location_id:
                continue

            existing = await ghl.get_session_storage().get_session(location_id)
            if not existing:
                location_token = await ghl.oauth.get_location_access_token(
                    request_body={'companyId': company_id, 'locationId': location_id},
                    options={'headers': {'companyId': company_id}}
                )
                # The location-token response is camelCase; normalize the token keys
                # the SDK reads (access_token / refresh_token) before storing.
                await ghl.get_session_storage().set_session(location_id, {
                    **location_token,
                    'access_token': location_token.get('accessToken'),
                    'refresh_token': location_token.get('refreshToken'),
                    'companyId': company_id,
                    'locationId': location_id,
                    'userType': 'Location',
                })

            resolved_location_id = resolved_location_id or location_id

        if resolved_location_id:
            return {'ready': True, 'locationId': resolved_location_id}
        return {'ready': False}

    try:
        result = run_async_in_loop(resolve_location())
        if result.get('ready'):
            # Location token resolved & stored; stop using the agency token so
            # subsequent location-scoped calls (e.g. /contact) use the location token.
            ghl.update_config({'agency_access_token': None})
        return jsonify(result)
    except Exception as err:
        print('Error resolving location token:', err)
        traceback.print_exc()
        return jsonify({'ready': False, 'error': str(err)})

@app.route('/oauth-result')
def oauth_result():
    """Show the resolved location token after the loading/polling step."""
    company_id = request.args.get('companyId')
    location_id = request.args.get('locationId')

    async def load_session():
        token = None
        if location_id:
            token = await ghl.get_session_storage().get_session(location_id)
        if not token and company_id:
            token = await ghl.get_session_storage().get_session(company_id)
        return token

    token = run_async_in_loop(load_session())
    if not token:
        return redirect(url_for('error_page', msg='No session found for the resolved location'))
    return render_template('token.html', token=token, location_id=location_id)

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

            search_result = await ghl.contacts.search_contacts_advanced(
                request_body={'locationId': resource_id, 'pageLimit': 5},
                options={'headers': {'locationId': resource_id}}
            )
            contacts = search_result.get('contacts', []) if isinstance(search_result, dict) else []
            print('Fetched contacts:', contacts)

            if not contacts:
                return {'error': 'No contact found'}

            contact_id = contacts[0]['id']
            contact_data = await ghl.contacts.get_contact(
                contact_id,
                options={'headers': {'locationId': resource_id}}
            )

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
                token_details.get('userType', 'Location')
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

# One read-only call per service for a locationId — a quick end-to-end check that
# the whole v3 SDK works. (label, service attribute, method name)
SERVICE_CALLS = [
    ("Contacts", "contacts", "search_contacts_advanced"),
    ("Calendars", "calendars", "get_calendars"),
    ("Campaigns", "campaigns", "get_campaigns"),
    ("Conversations", "conversations", "search_conversation"),
    ("Opportunities (Pipelines)", "opportunities", "get_pipelines"),
    ("Forms", "forms", "get_forms"),
    ("Funnels", "funnels", "get_funnels"),
    ("Links", "links", "get_links"),
    ("Location", "locations", "get_location"),
    ("Businesses", "businesses", "get_businesses_by_location"),
    ("Products", "products", "list_invoices"),
    ("Surveys", "surveys", "get_surveys"),
    ("Workflows", "workflows", "get_workflow"),
    ("Emails", "emails", "list_email_campaigns"),
    ("Brand Voices", "brand_boards", "list_brand_voices"),
    ("Affiliates", "affiliate_manager", "list_affiliates"),
    ("Payments (Config)", "payments", "fetch_config"),
    ("Phone System", "phone_system", "get_number_pool_list"),
    ("Proposals", "proposals", "list_documents_contracts"),
    ("Social Planner", "social_planner", "fetch_available_categories"),
    ("Knowledge Base", "knowledge_base", "list_all_knowledge_bases_paginated"),
    ("Custom Objects", "objects", "get_object_by_location_id"),
    ("Voice AI (Call Logs)", "voice_ai", "get_call_logs"),
    ("Custom Menus", "custom_menus", "get_custom_menus"),
]


def summarize_record(data):
    """Pull the first record out of an arbitrary SDK response and return a small
    list of (key, value) pairs to display, or None when there is no data."""
    record = None
    if isinstance(data, list):
        record = data[0] if data else None
    elif isinstance(data, dict):
        # 1) a collection under some key -> first item
        for value in data.values():
            if isinstance(value, list) and value:
                record = value[0]
                break
        # 2) the dict itself carries scalar fields -> use it
        if record is None and any(
            isinstance(v, (str, int, float, bool)) and v != "" for v in data.values()
        ):
            record = data
        # 3) otherwise a nested object under some key
        if record is None:
            for value in data.values():
                if isinstance(value, dict) and value:
                    record = value
                    break

    if not isinstance(record, dict) or not record:
        return None

    priority = ["id", "_id", "name", "firstName", "lastName", "email", "title",
                "type", "status", "locationId", "phone", "timezone", "dateAdded"]
    pairs = []
    for key in priority:
        value = record.get(key)
        if isinstance(value, (str, int, float, bool)) and value != "":
            pairs.append((key, value))
    if not pairs:
        for key, value in record.items():
            if isinstance(value, (str, int, float, bool)) and value != "":
                pairs.append((key, value))
            if len(pairs) >= 5:
                break
    return pairs or None


async def invoke_service_method(method, location_id):
    """Call a read-only service method, supplying location_id / request_body / options
    based on what the method actually accepts."""
    params = inspect.signature(method).parameters
    kwargs = {}
    if "location_id" in params:
        kwargs["location_id"] = location_id
    if "request_body" in params:
        kwargs["request_body"] = {"locationId": location_id, "pageLimit": 5}
    if "options" in params:
        kwargs["options"] = {"headers": {"locationId": location_id}}
    return await method(**kwargs)


@app.route('/show-data')
def show_data():
    """Call one read-only method from each service for the locationId and render a
    section per service — a quick end-to-end verification that the SDK works."""
    resource_id = request.args.get('resourceId')
    if not resource_id:
        return redirect(url_for('error_page', msg='No resourceId provided'))

    async def gather_all():
        async def call(label, service_attr, method_name):
            service = getattr(ghl, service_attr, None)
            method = getattr(service, method_name, None) if service else None
            if method is None:
                return {"label": label, "fields": None, "error": "method not available in SDK"}
            try:
                data = await invoke_service_method(method, resource_id)
                return {"label": label, "fields": summarize_record(data), "error": None}
            except Exception as error:
                return {"label": label, "fields": None, "error": str(error)}

        return await asyncio.gather(
            *(call(label, attr, name) for (label, attr, name) in SERVICE_CALLS)
        )

    try:
        sections = run_async_in_loop(gather_all())
    except Exception as error:
        print('Error building show-data:', error)
        traceback.print_exc()
        return redirect(url_for('error_page', msg=f'Error fetching data: {str(error)}'))

    return render_template('show_data.html', sections=sections, location_id=resource_id)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
