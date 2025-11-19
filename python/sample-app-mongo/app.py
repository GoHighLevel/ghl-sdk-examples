import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from highlevel import HighLevel
import traceback
from highlevel.storage import MongoDBSessionStorage
from typing import Optional

# Load environment variables
try:
    load_dotenv()
except Exception:
    pass  # Ignore if .env file doesn't exist or can't be read

# Configuration
PORT = int(os.getenv('PORT', '3003'))
CLIENT_ID = os.getenv('CLIENT_ID', '67f4fa36f25eeb6dc2636d6c-mdr0vmth')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '6fede484-bfc8-4210-994f-58d2a94974dc')

# Global app state
class AppState:
    def __init__(self):
        self.ghl: Optional[HighLevel] = None

app_state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown"""
    # Startup: Initialize HighLevel SDK
    try:
        app_state.ghl = HighLevel(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            log_level='debug',
            session_storage=MongoDBSessionStorage(
                os.getenv('MONGO_URL', 'mongodb://localhost:27017'),
                os.getenv('MONGO_DB_NAME', 'local'),
                os.getenv('COLLECTION_NAME', 'tokens')
            ))
        print("✅ HighLevel SDK initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize HighLevel SDK: {e}")
        # Continue without GHL for graceful degradation

    yield

    # Shutdown: Clean up resources
    if app_state.ghl:
        # Close any connections if needed
        print("🧹 Cleaning up HighLevel SDK connections")

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# Dependency injection for HighLevel SDK
async def get_ghl() -> HighLevel:
    """Dependency injection for HighLevel SDK instance"""
    if app_state.ghl is None:
        raise HTTPException(status_code=500, detail="HighLevel SDK not initialized")
    return app_state.ghl

def check_env(request: Request):
    """Check environment variables"""
    if request.url.path.startswith('/error-page'):
        return None

    if not CLIENT_ID or not CLIENT_ID.strip():
        return RedirectResponse(url=f'/error-page?msg=Please set CLIENT_ID env variable to proceed', status_code=302)

    if not CLIENT_SECRET or not CLIENT_SECRET.strip():
        return RedirectResponse(url=f'/error-page?msg=Please set CLIENT_SECRET env variable to proceed', status_code=302)

    return None

async def is_authorized(resource_id: str, ghl: HighLevel = Depends(get_ghl)):
    """Check if the resource is authorized"""
    session_data = await ghl.get_session_storage().get_session(resource_id)
    return session_data is not None

@app.middleware("http")
async def env_check_middleware(request: Request, call_next):
    """Environment check middleware"""
    env_check = check_env(request)
    if env_check:
        return env_check
    response = await call_next(request)
    return response

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.get('/install')
async def install(ghl: HighLevel = Depends(get_ghl)):
    redirect_uri = f"http://localhost:{PORT}/oauth-callback"
    authorization_url = ghl.oauth.get_authorization_url(
        CLIENT_ID,
        redirect_uri,
        'contacts.readonly contacts.write'
    )
    print('Redirect URL:', authorization_url)
    return RedirectResponse(url=authorization_url, status_code=302)

@app.get('/oauth-callback', response_class=HTMLResponse)
async def oauth_callback(request: Request, code: str = None, ghl: HighLevel = Depends(get_ghl)):
    """Handle OAuth callback"""
    if not code:
        return RedirectResponse(url=f'/error-page?msg=No code provided', status_code=302)

    try:
        access_token_data = await ghl.oauth.get_access_token({
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
        })
        print('Token:', access_token_data)

        await ghl.get_session_storage().set_session(access_token_data['locationId'], access_token_data)
        return templates.TemplateResponse('token.html', {
            'request': request,
            'token': access_token_data,
            'location_id': access_token_data['locationId']
        })
    except Exception as err:
        print('Error fetching token:', err)
        traceback.print_exc()
        return RedirectResponse(url=f'/error-page?msg=Error fetching token: {str(err)}', status_code=302)

@app.get('/contact', response_class=HTMLResponse)
async def contact(request: Request, resourceId: str = None, ghl: HighLevel = Depends(get_ghl)):
    """Handle contact retrieval"""
    try:
        if not resourceId:
            return RedirectResponse(url=f'/error-page?msg=No resourceId provided', status_code=302)

        # Check authorization
        authorized = await is_authorized(resourceId, ghl)
        if not authorized:
            return RedirectResponse(url=f'/error-page?msg=Please authorize the application to proceed', status_code=302)

        contacts_data = await ghl.contacts.get_contacts(resourceId, None, None, None, 5)
        print('Fetched contacts:', contacts_data['contacts'])

        contacts = contacts_data.get('contacts', [])
        if not contacts:
            return RedirectResponse(url=f'/error-page?msg=No contacts found', status_code=302)

        contact_id = contacts[0]['id']
        if not contact_id:
            return RedirectResponse(url=f'/error-page?msg=No contact found', status_code=302)

        contact_data = await ghl.contacts.get_contact(contact_id, {'headers': {'locationId': resourceId}})
        return templates.TemplateResponse('contact.html', {
            'request': request,
            'contact': contact_data.get('contact')
        })

    except Exception as error:
        print('Error fetching contact:', error)
        traceback.print_exc()
        return RedirectResponse(url='/', status_code=302)

@app.get('/refresh-token', response_class=HTMLResponse)
async def refresh_token(request: Request, resourceId: str = None, ghl: HighLevel = Depends(get_ghl)):
    """Handle token refresh"""
    try:
        if not resourceId:
            return RedirectResponse(url=f'/error-page?msg=No resourceId provided', status_code=302)

        token_details = await ghl.get_session_storage().get_session(resourceId)
        if not token_details:
            return RedirectResponse(url=f'/error-page?msg=No token found', status_code=302)

        refreshed_token = await ghl.oauth.refresh_token(
            token_details['refresh_token'],
            CLIENT_ID,
            CLIENT_SECRET,
            'refresh_token',
            token_details.get('user_type', 'Location')
        )
        await ghl.get_session_storage().set_session(resourceId, refreshed_token)
        return templates.TemplateResponse('token.html', {
            'request': request,
            'token': refreshed_token,
            'location_id': resourceId
        })

    except Exception as error:
        print('Error refreshing token:', error)
        traceback.print_exc()
        return RedirectResponse(url=f'/error-page?msg=Error refreshing token', status_code=302)

@app.get('/error-page', response_class=HTMLResponse)
async def error_page(request: Request, msg: str = 'Unknown error'):
    return templates.TemplateResponse('error.html', {'request': request, 'error': msg})

if __name__ == '__main__':
    import uvicorn
    print(f"Starting FastAPI server on http://0.0.0.0:{PORT}")
    uvicorn.run(app, host='0.0.0.0', port=PORT)
