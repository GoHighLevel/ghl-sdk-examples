<?php

require_once __DIR__ . '/../vendor/autoload.php';

use Slim\Factory\AppFactory;
use Slim\Views\Twig;
use Slim\Views\TwigMiddleware;
use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;
use Psr\Http\Server\RequestHandlerInterface as RequestHandler;
use Dotenv\Dotenv;
use Monolog\Logger;
use Monolog\Handler\StreamHandler;

// HighLevel SDK imports
use HighLevel\HighLevel;
use HighLevel\Storage\SessionData;

// Load environment variables
$dotenv = Dotenv::createImmutable(__DIR__ . '/..');
$dotenv->safeLoad();

// Configuration
$config = [
    'port' => $_ENV['PORT'] ?? 8000,
    'client_id' => $_ENV['CLIENT_ID'] ?? '',
    'client_secret' => $_ENV['CLIENT_SECRET'] ?? '',
    'mongo_url' => $_ENV['MONGO_URL'] ?? 'mongodb://localhost:27017',
    'mongo_db_name' => $_ENV['MONGO_DB_NAME'] ?? 'ghl_sessions',
    'collection_name' => $_ENV['COLLECTION_NAME'] ?? 'sessions',
    'debug' => ($_ENV['DEBUG'] ?? 'false') === 'true',
    'log_level' => $_ENV['LOG_LEVEL'] ?? 'info'
];

// Create Slim app
$app = AppFactory::create();

// Error handling
$app->addErrorMiddleware($config['debug'], true, true);

// Setup Twig
$twig = Twig::create(__DIR__ . '/../templates', ['cache' => false]);
$app->add(TwigMiddleware::create($app, $twig));

// Setup logging
$logger = new Logger('ghl-app');
$logger->pushHandler(new StreamHandler('php://stdout', Logger::WARNING));

// Initialize HighLevel SDK with MongoDB session storage
try {

    $ghl = new HighLevel([
        'clientId' => $config['client_id'],
        'clientSecret' => $config['client_secret'],
        'logLevel' => 'info'
    ]);

    $logger->info('HighLevel SDK initialized successfully');
} catch (Exception $e) {
    $logger->error('Failed to initialize HighLevel SDK: ' . $e->getMessage());
    throw $e;
}

// Middleware to check environment variables
$checkEnv = function (Request $request, RequestHandler $handler): Response {
    global $config;

    $path = $request->getUri()->getPath();
    if (strpos($path, '/error-page') === 0) {
        return $handler->handle($request);
    }

    if (empty($config['client_id'])) {
        return (new \Slim\Psr7\Response(302))
            ->withHeader('Location', '/error-page?msg=' . urlencode('Please set CLIENT_ID environment variable to proceed'));
    }

    if (empty($config['client_secret'])) {
        return (new \Slim\Psr7\Response(302))
            ->withHeader('Location', '/error-page?msg=' . urlencode('Please set CLIENT_SECRET environment variable to proceed'));
    }

    return $handler->handle($request);
};

// Helper function to check if user is authorized
function isAuthorized(string $resourceId, HighLevel $ghl): bool
{
    try {
        $session = $ghl->getSessionStorage()->getSession($resourceId);
        return $session !== null;
    } catch (Exception $e) {
        error_log('Error checking authorization: ' . $e->getMessage());
        return false;
    }
}

// Apply middleware
$app->add($checkEnv);

// Routes
$app->get('/', function (Request $request, Response $response, array $args) {
    $view = Twig::fromRequest($request);
    return $view->render($response, 'index.twig');
});

$app->get('/install', function (Request $request, Response $response, array $args) use ($ghl, $config) {
    try {
        $redirectUrl = $ghl->oauth->getAuthorizationUrl(
            $config['client_id'],
            "http://localhost:{$config['port']}/oauth-callback",
            'contacts.readonly contacts.write oauth.write oauth.readonly'
        );

        error_log('Redirect URL: ' . $redirectUrl);

        return $response->withHeader('Location', $redirectUrl)->withStatus(302);
    } catch (Exception $e) {
        error_log('Error generating authorization URL: ' . $e->getMessage());
        return $response->withHeader('Location', '/error-page?msg=' . urlencode('Error generating authorization URL'))->withStatus(302);
    }
});

$app->get('/oauth-callback', function (Request $request, Response $response, array $args) use ($ghl, $config) {
    $queryParams = $request->getQueryParams();
    $code = $queryParams['code'] ?? null;

    if (!$code) {
        return $response->withHeader('Location', '/error-page?msg=' . urlencode('No code provided'))->withStatus(302);
    }

    try {
        // v3 OAuth token endpoint expects camelCase body fields
        $accessToken = $ghl->oauth->getAccessToken([
            'clientId' => $config['client_id'],
            'clientSecret' => $config['client_secret'],
            'code' => $code,
            'grantType' => 'authorization_code'
        ]);
        
        error_log('Token received: ' . json_encode($accessToken, JSON_PRETTY_PRINT));

        $locationId = $accessToken->location_id ?? null;
        $companyId = $accessToken->company_id ?? null;

        // Sub-account install: the token response already carries a locationId,
        // so store it and show the token straight away.
        if ($locationId) {
            $ghl->getSessionStorage()->setSession($locationId, new SessionData($accessToken));

            $view = Twig::fromRequest($request);
            return $view->render($response, 'token.twig', [
                'token' => $accessToken,
                'locationId' => $locationId,
            ]);
        }

        // Company (agency) install: no locationId in the token (it's a company
        // token). Store the company token, then show a loading screen that polls
        // get-installed-location until location tokens can be generated.
        if (!$companyId) {
            throw new Exception('No locationId or companyId found in token response');
        }

        $ghl->getSessionStorage()->setSession($companyId, new SessionData($accessToken));

        $view = Twig::fromRequest($request);
        return $view->render($response, 'loading.twig', [
            'companyId' => $companyId,
        ]);
    } catch (Exception $e) {
        error_log('Error fetching token: ' . $e->getMessage());
        return $response->withHeader('Location', '/error-page?msg=' . urlencode('Error fetching token: ' . $e->getMessage()))->withStatus(302);
    }
});

$app->get('/install-locations', function (Request $request, Response $response, array $args) use ($ghl, $config) {
    $companyId = $request->getQueryParams()['companyId'] ?? null;

    $respondJson = function (array $payload) use ($response) {
        $response->getBody()->write(json_encode($payload));
        return $response->withHeader('Content-Type', 'application/json');
    };

    if (!$companyId) {
        return $respondJson(['ready' => false, 'error' => 'No companyId provided']);
    }

    try {
        // GHL OAuth client id is "<appId>-<random>"; appId is the part before "-".
        $appId = explode('-', $config['client_id'])[0];

        // SDK auto-resolves the company token from storage via companyId.
        $installed = $ghl->oauth->getInstalledLocation([
            'companyId' => $companyId,
            'appId' => $appId,
            'isInstalled' => 'true',
        ]);

        $items = $installed->items ?? [];

        $generated = [];
        $available = [];
        foreach ($items as $item) {
            // InstalledLocationSchema "_id" maps to the model's $id property.
            $locId = $item->id ?? null;
            if (!$locId) {
                continue;
            }

            // Token already exists for this location — skip generation.
            if ($ghl->getSessionStorage()->getSession($locId)) {
                $available[] = $locId;
                continue;
            }

            // Generate a location token using the company token.
            $locationToken = $ghl->oauth->getLocationAccessToken([
                'companyId' => $companyId,
                'locationId' => $locId,
            ]);
            $ghl->getSessionStorage()->setSession($locId, new SessionData($locationToken));
            $generated[] = $locId;
            $available[] = $locId;
        }

        // Prefer a location we just generated a token for; otherwise the first
        // location that already had one. Keep polling until at least one exists.
        $picked = $generated[0] ?? ($available[0] ?? null);

        return $respondJson([
            'ready' => $picked !== null,
            'locationId' => $picked,
            'generated' => $generated,
            'count' => count($available),
        ]);
    } catch (Exception $e) {
        error_log('Error resolving installed locations: ' . $e->getMessage());
        // Keep the client polling on transient errors.
        return $respondJson(['ready' => false, 'error' => $e->getMessage()]);
    }
});

// Final screen for a company install: shows the company token + the location id
// that was resolved/generated during polling.
$app->get('/oauth-result', function (Request $request, Response $response, array $args) use ($ghl) {
    $queryParams = $request->getQueryParams();
    $companyId = $queryParams['companyId'] ?? null;
    $locationId = $queryParams['locationId'] ?? null;

    $token = $companyId ? $ghl->getSessionStorage()->getSession($companyId) : null;

    $view = Twig::fromRequest($request);
    return $view->render($response, 'token.twig', [
        'token' => $token,
        'locationId' => $locationId,
    ]);
});

$app->get('/contact', function (Request $request, Response $response, array $args) use ($ghl) {
    try {
        $queryParams = $request->getQueryParams();
        $resourceId = $queryParams['resourceId'] ?? null;

        if (!$resourceId) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('No resourceId provided'))->withStatus(302);
        }

        if (!isAuthorized($resourceId, $ghl)) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('Please authorize the application to proceed'))->withStatus(302);
        }

        // v3 replaced the list endpoint with advanced search (POST /contacts/search).
        $searchResult = $ghl->contacts->searchContactsAdvanced([
            'locationId' => $resourceId,
            'pageLimit' => 5
        ]);

        error_log('Fetched contacts: ' . json_encode($searchResult, JSON_PRETTY_PRINT));

        // searchContactsAdvanced returns the raw response array.
        $contacts = $searchResult['contacts'] ?? [];
        if (empty($contacts)) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('No contacts found'))->withStatus(302);
        }

        $contactId = $contacts[0]['id'] ?? null;
        if (!$contactId) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('No contact id found'))->withStatus(302);
        }

        // Fetch individual contact details
        $contactResponse = $ghl->contacts->getContact([
            'contactId' => $contactId
        ], [
            'headers' => [
                'locationId' => $resourceId
            ]
        ]);

        error_log('Contact details: ' . json_encode($contactResponse, JSON_PRETTY_PRINT));

        $contact = $contactResponse->contact ?? null;

        $view = Twig::fromRequest($request);
        return $view->render($response, 'contact.twig', [
            'contact' => $contact
        ]);
    } catch (Exception $e) {
        error_log('Error fetching contact: ' . $e->getMessage());
        return $response->withHeader('Location', '/error-page?msg=' . urlencode('Error fetching contact: ' . $e->getMessage()))->withStatus(302);
    }
});

$app->get('/refresh-token', function (Request $request, Response $response, array $args) use ($ghl, $config) {
    try {
        $queryParams = $request->getQueryParams();
        $resourceId = $queryParams['resourceId'] ?? null;

        if (!$resourceId) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('No resourceId provided'))->withStatus(302);
        }

        $tokenDetails = $ghl->getSessionStorage()->getSession($resourceId);
        if (!$tokenDetails) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('No token found'))->withStatus(302);
        }

        $refreshToken = $tokenDetails->refresh_token;
        $userType = $tokenDetails->userType ?? 'Location';

        // Use the real SDK to refresh the token
        $newToken = $ghl->oauth->refreshToken(
            $refreshToken,
            $config['client_id'],
            $config['client_secret'],
            'refresh_token',
            $userType
        );

        error_log('Refreshed token: ' . json_encode($newToken, JSON_PRETTY_PRINT));

        // Update the session storage with new token
        $ghl->getSessionStorage()->setSession($resourceId, new SessionData($newToken));

        $view = Twig::fromRequest($request);
        return $view->render($response, 'token.twig', [ 'token' => $newToken ]);
    } catch (Exception $e) {
        error_log('Error refreshing token: ' . $e->getMessage());
        return $response->withHeader('Location', '/error-page?msg=' . urlencode('Error refreshing token: ' . $e->getMessage()))->withStatus(302);
    }
});

$app->get('/error-page', function (Request $request, Response $response, array $args) {
    $queryParams = $request->getQueryParams();
    $error = $queryParams['msg'] ?? 'An unexpected error occurred';

    $view = Twig::fromRequest($request);
    return $view->render($response, 'error.twig', [
        'error' => $error
    ]);
});

$app->run();
