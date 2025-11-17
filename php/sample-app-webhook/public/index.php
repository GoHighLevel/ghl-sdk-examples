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
use HighLevel\Services\Contacts\Models\SearchBodyV2DTO;
use HighLevel\Storage\SessionData;
use HighLevel\Storage\MongoDBSessionStorage;

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
    'log_level' => $_ENV['LOG_LEVEL'] ?? 'info',
    'webhook_public_key' => $_ENV['WEBHOOK_PUBLIC_KEY'] ?? ''
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
$logger->pushHandler(new StreamHandler('php://stdout', \Monolog\Level::Warning));

// Initialize HighLevel SDK with MongoDB session storage
try {

    $ghl = new HighLevel([
        'clientId' => $config['client_id'],
        'clientSecret' => $config['client_secret'],
        'logLevel' => 'info',
        'sessionStorage' => new MongoDBSessionStorage(
            $config['mongo_url'],
            $config['mongo_db_name'],
            $config['collection_name']
        )
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
            'contacts.readonly contacts.write voice-ai-dashboard.readonly'
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
        $accessToken = $ghl->oauth->getAccessToken([
            'client_id' => $config['client_id'],
            'client_secret' => $config['client_secret'],
            'code' => $code,
            'grant_type' => 'authorization_code'
        ]);
        
        error_log('Token received: ' . json_encode($accessToken, JSON_PRETTY_PRINT));

        // Store the token using the session storage
        $locationId = $accessToken->location_id ?? $accessToken->company_id;
        if (!$locationId) {
            throw new Exception('No locationId or companyId found in token response');
        }

        $ghl->getSessionStorage()->setSession($locationId, new SessionData($accessToken));

        $view = Twig::fromRequest($request);
        return $view->render($response, 'token.twig', [
            'token' => $accessToken
        ]);
    } catch (Exception $e) {
        error_log('Error fetching token: ' . $e->getMessage());
        return $response->withHeader('Location', '/error-page?msg=' . urlencode('Error fetching token: ' . $e->getMessage()))->withStatus(302);
    }
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

        $requestBody = new SearchBodyV2DTO([
            'locationId' => $resourceId,
            'pageLimit' => 1
        ]);
        $contactsResponse = $ghl->contacts->searchContactsAdvanced($requestBody);

        error_log('Fetched contacts: ' . json_encode($contactsResponse, JSON_PRETTY_PRINT));

        $contacts = $contactsResponse['contacts'] ?? [];
        if (empty($contacts)) {
            return $response->withHeader('Location', '/error-page?msg=' . urlencode('No contacts found'))->withStatus(302);
        }

        $contactId = $contacts[0]['id'];

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

        // Test voice AI call logs api to get the data
        $voiceAiCallLogs = $ghl->voiceAi->getCallLogs([
            'locationId' => $resourceId
        ]);

        error_log('Voice AI call logs: ' . json_encode($voiceAiCallLogs, JSON_PRETTY_PRINT));

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
        $userType = $tokenDetails->user_type ?? 'Location';

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

$webhookMiddleware = function (Request $request, RequestHandler $handler) use ($ghl, $config) {
    $payload = $request->getBody()->getContents();
    $signature = $request->getHeaderLine('x-wh-signature');

    // Process with your WebhookManager
    $result = $ghl->getWebhookManager()->processWebhook($payload, $signature, $config['webhook_public_key'], $config['client_id']);
    
    // Add result to request attributes
    $request = $request->withAttribute('webhook_result', $result);
    
    // Continue to next middleware/route
    return $handler->handle($request);
};

// Your application route with middleware applied only to this route
$app->post('/api/ghl/webhook', function (Request $request, Response $response) {
    $webhookResult = $request->getAttribute('webhook_result');

    error_log('Webhook result: ' . json_encode($webhookResult, JSON_PRETTY_PRINT));
    
    if ($webhookResult['processed']) {
        // Handle successful webhook
        error_log('Webhook processed successfully');
    }
    
    $response->getBody()->write(json_encode(['success' => true]));
    return $response->withStatus(200)->withHeader('Content-Type', 'application/json');
})->add($webhookMiddleware);

$app->run();
