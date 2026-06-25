from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from highlevel import HighLevel
from highlevel.storage import MongoDBSessionStorage
import traceback

# Global HighLevel instance - Django handles async properly
ghl = None

async def initialize_ghl():
    """Initialize the global HighLevel instance with MongoDB storage"""
    global ghl
    if ghl is None:
        ghl = HighLevel(
            client_id=settings.CLIENT_ID,
            client_secret=settings.CLIENT_SECRET,
            log_level='debug',
            session_storage=MongoDBSessionStorage(
                settings.MONGO_URL,
                settings.MONGO_DB_NAME,
                settings.COLLECTION_NAME
            ))

        # Initialize MongoDB storage
        if hasattr(ghl.session_storage, 'init'):
            await ghl.session_storage.init()

def check_env(request):
    """Middleware to check environment variables"""
    if request.path.startswith('/error-page'):
        return None

    if not settings.CLIENT_ID or not settings.CLIENT_ID.strip():
        return redirect(reverse('error_page') + '?msg=Please set CLIENT_ID env variable to proceed')

    if not settings.CLIENT_SECRET or not settings.CLIENT_SECRET.strip():
        return redirect(reverse('error_page') + '?msg=Please set CLIENT_SECRET env variable to proceed')

    return None

async def is_authorized(resource_id):
    """Check if the resource is authorized"""
    global ghl
    if ghl is None:
        await initialize_ghl()
    session_data = await ghl.get_session_storage().get_session(resource_id)
    return session_data is not None

async def index(request):
    """Home page"""
    env_check = check_env(request)
    if env_check:
        return env_check

    return render(request, 'index.html')

async def install(request):
    """OAuth install route"""
    env_check = check_env(request)
    if env_check:
        return env_check

    global ghl
    if ghl is None:
        await initialize_ghl()
    redirect_uri = f"http://localhost:{settings.PORT}/oauth-callback"
    authorization_url = ghl.oauth.get_authorization_url(
        settings.CLIENT_ID,
        redirect_uri,
        'contacts.readonly contacts.write oauth.readonly oauth.write'
    )
    print('Redirect URL:', authorization_url)
    return redirect(authorization_url)

async def oauth_callback(request):
    """Handle OAuth callback"""
    code = request.GET.get('code')
    if not code:
        return redirect(reverse('error_page') + '?msg=No code provided')

    try:
        global ghl
        if ghl is None:
            await initialize_ghl()
        access_token_data = await ghl.oauth.get_access_token({
            'clientId': settings.CLIENT_ID,
            'clientSecret': settings.CLIENT_SECRET,
            'code': code,
            'grantType': 'authorization_code',
        })
        print('Token:', access_token_data)

        location_id = access_token_data.get('locationId')
        if location_id:
            await ghl.get_session_storage().set_session(location_id, access_token_data)
            return render(request, 'token.html', {
                'token': access_token_data,
                'location_id': location_id
            })

        # Company (agency) level install: store the company token and poll for a
        # location token via the loading page.
        company_id = access_token_data.get('companyId')
        if not company_id:
            return redirect(reverse('error_page') + '?msg=Token response had neither locationId nor companyId')

        await ghl.get_session_storage().set_session(company_id, access_token_data)
        # Make the agency (company) token available to the agency-scoped polling calls
        # directly via config (checked before storage). Cleared once a location resolves.
        ghl.update_config({
            'agency_access_token': access_token_data.get('accessToken') or access_token_data.get('access_token')
        })
        return render(request, 'loading.html', {'company_id': company_id})
    except Exception as err:
        print('Error fetching token:', err)
        traceback.print_exc()
        return redirect(reverse('error_page') + f'?msg=Error fetching token: {str(err)}')

async def install_locations(request):
    """Poll endpoint: resolve a location token from the company token (JSON)."""
    global ghl
    if ghl is None:
        await initialize_ghl()

    company_id = request.GET.get('companyId')
    if not company_id:
        return JsonResponse({'ready': False, 'error': 'No companyId provided'})

    try:
        app_id = (settings.CLIENT_ID or '').split('-')[0]
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
                # The location-token response is camelCase; normalize the keys the
                # SDK reads (access_token / refresh_token) before storing.
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
            # Stop using the agency token now that a location token is stored, so
            # subsequent location-scoped calls (e.g. /contact) use the location token.
            ghl.update_config({'agency_access_token': None})
            return JsonResponse({'ready': True, 'locationId': resolved_location_id})
        return JsonResponse({'ready': False})
    except Exception as error:
        print('Error resolving location token:', error)
        traceback.print_exc()
        return JsonResponse({'ready': False, 'error': str(error)})


async def oauth_result(request):
    """Show the resolved location token after the loading/polling step."""
    global ghl
    if ghl is None:
        await initialize_ghl()

    company_id = request.GET.get('companyId')
    location_id = request.GET.get('locationId')

    token = None
    if location_id:
        token = await ghl.get_session_storage().get_session(location_id)
    if not token and company_id:
        token = await ghl.get_session_storage().get_session(company_id)

    if not token:
        return redirect(reverse('error_page') + '?msg=No session found for the resolved location')
    return render(request, 'token.html', {'token': token, 'location_id': location_id})


async def contact(request):
    """Handle contact retrieval"""
    env_check = check_env(request)
    if env_check:
        return env_check

    try:
        resource_id = request.GET.get('resourceId')
        if not resource_id:
            return redirect(reverse('error_page') + '?msg=No resourceId provided')

        # Check authorization
        authorized = await is_authorized(resource_id)
        if not authorized:
            return redirect(reverse('error_page') + '?msg=Please authorize the application to proceed')

        global ghl
        if ghl is None:
            await initialize_ghl()
        search_result = await ghl.contacts.search_contacts_advanced(
            request_body={'locationId': resource_id, 'pageLimit': 5},
            options={'headers': {'locationId': resource_id}}
        )
        contacts = search_result.get('contacts', []) if isinstance(search_result, dict) else []
        print('Fetched contacts:', contacts)

        if not contacts:
            return redirect(reverse('error_page') + '?msg=No contacts found')

        contact_id = contacts[0]['id']
        contact_data = await ghl.contacts.get_contact(contact_id, options={'headers': {'locationId': resource_id}})
        return render(request, 'contact.html', {'contact': contact_data.get('contact')})

    except Exception as error:
        print('Error fetching contact:', error)
        traceback.print_exc()
        return redirect('index')

async def refresh_token(request):
    """Handle token refresh"""
    env_check = check_env(request)
    if env_check:
        return env_check

    try:
        resource_id = request.GET.get('resourceId')
        if not resource_id:
            return redirect(reverse('error_page') + '?msg=No resourceId provided')

        global ghl
        if ghl is None:
            await initialize_ghl()
        token_details = await ghl.get_session_storage().get_session(resource_id)
        if not token_details:
            return redirect(reverse('error_page') + '?msg=No token found')

        refreshed_token = await ghl.oauth.refresh_token(
            token_details['refresh_token'],
            settings.CLIENT_ID,
            settings.CLIENT_SECRET,
            'refresh_token',
            token_details.get('userType', 'Location')
        )
        await ghl.get_session_storage().set_session(resource_id, refreshed_token)
        return render(request, 'token.html', {
            'token': refreshed_token,
            'location_id': resource_id
        })

    except Exception as error:
        print('Error refreshing token:', error)
        traceback.print_exc()
        return redirect(reverse('error_page') + '?msg=Error refreshing token')

@csrf_exempt
async def webhook(request):
    """Handle GHL webhook"""
    if request.method != 'POST':
        return HttpResponseBadRequest('Method not allowed')

    try:
        global ghl
        if ghl is None:
            await initialize_ghl()
        webhook_middleware = ghl.webhooks.subscribe()
        await webhook_middleware(request)

        if getattr(request, 'is_signature_valid', False):
            print('Signature valid...., processing webhook data...')
            print('Signature type:', getattr(request, 'signature_type'))
            return JsonResponse({
                'status': 'success',
                'message': 'Webhook processed successfully',
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid signature, webhook not processed'
            }, status=400)

    except Exception as error:
        print('Error processing webhook:', error)
        traceback.print_exc()
        return JsonResponse({
            'error': f'Error processing webhook: {str(error)}'
        }, status=500)

async def error_page(request):
    """Error page"""
    error_msg = request.GET.get('msg', 'Unknown error')
    return render(request, 'error.html', {'error': error_msg})
