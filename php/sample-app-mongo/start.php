<?php

require_once __DIR__ . '/vendor/autoload.php';

use Dotenv\Dotenv;

// Load environment variables
$dotenv = Dotenv::createImmutable(__DIR__);
$dotenv->load(); // Use load() instead of safeLoad() to override existing env vars

$port = $_ENV['PORT'] ?? 3003;
$host = 'localhost';

echo "Starting PHP development server on http://{$host}:{$port}\n";
echo "Document root: " . __DIR__ . "/public\n";
echo "Press Ctrl+C to stop the server\n\n";

$phpCommand = 'php';

// Start the PHP development server
$command = "{$phpCommand} -S {$host}:{$port} public/index.php";
echo "Running: {$command}\n\n";
passthru($command);
