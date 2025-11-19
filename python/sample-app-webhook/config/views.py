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
        'contacts.readonly contacts.write'
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
            'client_id': settings.CLIENT_ID,
            'client_secret': settings.CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
        })
        print('Token:', access_token_data)

        await ghl.get_session_storage().set_session(access_token_data['locationId'], access_token_data)
        return render(request, 'token.html', {
            'token': access_token_data,
            'location_id': access_token_data['locationId']
        })
    except Exception as err:
        print('Error fetching token:', err)
        traceback.print_exc()
        return redirect(reverse('error_page') + f'?msg=Error fetching token: {str(err)}')

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
        contacts_data = await ghl.contacts.get_contacts(resource_id, None, None, None, 5)
        print('Fetched contacts:', contacts_data['contacts'])

        contacts = contacts_data.get('contacts', [])
        if not contacts:
            return redirect(reverse('error_page') + '?msg=No contacts found')

        contact_id = contacts[0]['id']
        if not contact_id:
            return redirect(reverse('error_page') + '?msg=No contact found')

        contact_data = await ghl.contacts.get_contact(contact_id, {'headers': {'locationId': resource_id}})
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
            token_details.get('user_type', 'Location')
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
