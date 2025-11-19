import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from highlevel import HighLevel

# Load environment variables
try:
    load_dotenv()
except Exception:
    pass  # Ignore if .env file doesn't exist or can't be read

PORT = int(os.getenv('PORT', 3000))
PRIVATE_INTEGRATION_TOKEN = os.getenv('PRIVATE_INTEGRATION_TOKEN')

# Initialize HighLevel SDK (will be None if token not available)
ghl = None
if PRIVATE_INTEGRATION_TOKEN:
    ghl = HighLevel(
        private_integration_token=PRIVATE_INTEGRATION_TOKEN,
    )

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.middleware("http")
async def check_env_middleware(request: Request, call_next):
    """Middleware to check environment variables"""
    if request.url.path.startswith('/error-page'):
        return await call_next(request)

    if not PRIVATE_INTEGRATION_TOKEN or not PRIVATE_INTEGRATION_TOKEN.strip():
        # Redirect to error page
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f'/error-page?msg=Please set PRIVATE_INTEGRATION_TOKEN env variable to proceed')

    response = await call_next(request)
    return response

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.get('/contact', response_class=HTMLResponse)
async def contact(request: Request):
    if not ghl:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url='/error-page?msg=PRIVATE_INTEGRATION_TOKEN not configured')

    try:
        contact_id = 'zBG0T99IsBgOoXUrcROH'
        contact = await ghl.contacts.get_contact(contact_id=contact_id)
        print('Contact:', contact)
        return templates.TemplateResponse('contact.html', {'request': request, 'contact': contact.get('contact')})
    except Exception as error:
        print('Error fetching contact:', error)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url='/')

@app.get('/error-page', response_class=HTMLResponse)
async def error_page(request: Request, msg: str = 'Unknown error'):
    return templates.TemplateResponse('error.html', {'request': request, 'error': msg})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=PORT)
