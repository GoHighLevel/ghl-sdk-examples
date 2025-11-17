<?php

namespace HighLevel\Storage;

use HighLevel\Storage\SessionStorage;
use HighLevel\Storage\SessionData;
use HighLevel\Logging\Logger;
use PDO;
use PDOException;
use Exception;

/**
 * SQL/MySQL implementation of SessionStorage
 * Stores OAuth tokens and session data in MySQL database
 * 
 * @package HighLevel\Storage
 */
class SqlStorage extends SessionStorage
{
    /**
     * PDO database connection
     * @var PDO|null
     */
    private ?PDO $client = null;

    /**
     * OAuth client ID
     * @var string|null
     */
    private ?string $clientId = null;

    /**
     * Database configuration
     * @var array
     */
    private array $config;

    /**
     * Default collection/table name
     * @var string
     */
    private string $defaultCollection = 'ghl_sessions';

    /**
     * Create new SqlStorage instance
     * 
     * @param string $host Database host
     * @param string $database Database name
     * @param string $username Database username
     * @param string $password Database password
     * @param string $port Database port
     * @param string $charset Database charset
     * @param Logger|null $logger Logger instance
     */
    public function __construct(
        string $host = 'localhost',
        string $database = 'ghl_sessions',
        string $username = 'root',
        string $password = '',
        string $port = '3306',
        string $charset = 'utf8mb4',
        ?Logger $logger = null
    ) {
        parent::__construct($logger);

        $this->config = [
            'host' => $host,
            'database' => $database,
            'username' => $username,
            'password' => $password,
            'port' => $port,
            'charset' => $charset
        ];
    }

    /**
     * Set the client ID
     * 
     * @param string $clientId OAuth client ID
     * @return void
     */
    public function setClientId(string $clientId): void
    {
        $this->clientId = $clientId;
    }

    /**
     * Initialize database connection and create tables
     * 
     * @return void
     * @throws Exception If connection fails
     */
    public function init(): void
    {
        try {
            $dsn = "mysql:host={$this->config['host']};port={$this->config['port']};dbname={$this->config['database']};charset={$this->config['charset']}";
            
            $this->client = new PDO($dsn, $this->config['username'], $this->config['password'], [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ]);

            $this->logger->debug('SqlStorage: Database connection established');
            
            // Create default sessions table
            $this->createCollection($this->defaultCollection);
            
        } catch (PDOException $e) {
            $this->logger->error('SqlStorage: Failed to connect to database: ' . $e->getMessage());
            throw new Exception('Failed to connect to database: ' . $e->getMessage());
        }
    }

    /**
     * Close database connection
     * 
     * @return void
     */
    public function disconnect(): void
    {
    $this->client = null;
        $this->logger->debug('SqlStorage: Database connection closed');
    }

    /**
     * Create sessions table if it doesn't exist
     * 
     * @param string $collectionName Table name
     * @return void
     * @throws Exception If table creation fails
     */
    public function createCollection(string $collectionName): void
    {
        try {
            $sql = "
                CREATE TABLE IF NOT EXISTS `{$collectionName}` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `resource_id` VARCHAR(255) NOT NULL UNIQUE,
                    `client_id` VARCHAR(255),
                    `access_token` TEXT,
                    `refresh_token` TEXT,
                    `token_type` VARCHAR(50),
                    `scope` TEXT,
                    `user_type` VARCHAR(50),
                    `company_id` VARCHAR(255),
                    `location_id` VARCHAR(255),
                    `expire_at` BIGINT,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX `idx_resource_id` (`resource_id`),
                    INDEX `idx_client_id` (`client_id`),
                    INDEX `idx_expire_at` (`expire_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ";
            
            $this->client->exec($sql);
            $this->logger->debug("SqlStorage: Table '{$collectionName}' created or verified");
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to create table '{$collectionName}': " . $e->getMessage());
            throw new Exception("Failed to create table '{$collectionName}': " . $e->getMessage());
        }
    }

    /**
     * Get table reference (returns table name for SQL)
     * 
     * @param string $collectionName Table name
     * @return string Table name
     */
    public function getCollection(string $collectionName): string
    {
        return $collectionName;
    }

    /**
     * Store session data
     * 
     * @param string $resourceId Resource identifier
     * @param SessionData $sessionData Session data to store
     * @return void
     * @throws Exception If storage fails
     */
    public function setSession(string $resourceId, SessionData $sessionData): void
    {
        try {
            $sql = "
                INSERT INTO `{$this->defaultCollection}` (
                    resource_id, client_id, access_token, refresh_token, token_type,
                    scope, user_type, company_id, location_id, expire_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                    access_token = VALUES(access_token),
                    refresh_token = VALUES(refresh_token),
                    token_type = VALUES(token_type),
                    scope = VALUES(scope),
                    user_type = VALUES(user_type),
                    company_id = VALUES(company_id),
                    location_id = VALUES(location_id),
                    expire_at = VALUES(expire_at),
                    updated_at = CURRENT_TIMESTAMP
            ";
            $expireAt = null;
            if (isset($sessionData->expires_in)) {
                $expireAt = $this->calculateExpireAt($sessionData->expires_in);
            }
            $stmt = $this->client->prepare($sql);
            $stmt->execute([
                $resourceId,
                $this->clientId,
                $sessionData->access_token,
                $sessionData->refresh_token,
                $sessionData->token_type,
                $sessionData->scope,
                $sessionData->user_type,
                $sessionData->company_id,
                $sessionData->location_id,
                $expireAt
            ]);

            $this->logger->debug("SqlStorage: Session stored for resource ID: {$resourceId}");
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to store session for {$resourceId}: " . $e->getMessage());
            throw new Exception("Failed to store session: " . $e->getMessage());
        }
    }

    /**
     * Retrieve session data
     * 
     * @param string $resourceId Resource identifier
     * @return SessionData|null Session data or null if not found
     */
    public function getSession(string $resourceId): ?SessionData
    {
        try {
            $sql = "SELECT * FROM `{$this->defaultCollection}` WHERE resource_id = ? AND (client_id = ? OR client_id IS NULL)";
            $stmt = $this->client->prepare($sql);
            $stmt->execute([$resourceId, $this->clientId]);
            $row = $stmt->fetch();

            if (!$row) {
                $this->logger->debug("SqlStorage: No session found for resource ID: {$resourceId}");
                return null;
            }

            // Create ISessionData from database row
            $sessionData = new SessionData();
            $sessionData->access_token = $row['access_token'];
            $sessionData->refresh_token = $row['refresh_token'];
            $sessionData->token_type = $row['token_type'];
            $sessionData->scope = $row['scope'];
            $sessionData->user_type = $row['user_type'];
            $sessionData->company_id = $row['company_id'];
            $sessionData->location_id = $row['location_id'];
            $sessionData->expire_at = $row['expire_at'];

            $this->logger->debug("SqlStorage: Session retrieved for resource ID: {$resourceId}");
            return $sessionData;
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to retrieve session for {$resourceId}: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Delete session data
     * 
     * @param string $resourceId Resource identifier
     * @return void
     */
    public function deleteSession(string $resourceId): void
    {
        try {
            $sql = "DELETE FROM `{$this->defaultCollection}` WHERE resource_id = ? AND (client_id = ? OR client_id IS NULL)";
            $stmt = $this->client->prepare($sql);
            $stmt->execute([$resourceId, $this->clientId]);

            $this->logger->debug("SqlStorage: Session deleted for resource ID: {$resourceId}");
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to delete session for {$resourceId}: " . $e->getMessage());
        }
    }

    /**
     * Get access token only
     * 
     * @param string $resourceId Resource identifier
     * @return string|null Access token or null if not found
     */
    public function getAccessToken(string $resourceId): ?string
    {
        try {
            $sql = "SELECT access_token FROM `{$this->defaultCollection}` WHERE resource_id = ? AND (client_id = ? OR client_id IS NULL)";
            $stmt = $this->client->prepare($sql);
            $stmt->execute([$resourceId, $this->clientId]);
            $row = $stmt->fetch();

            return $row ? $row['access_token'] : null;
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to get access token for {$resourceId}: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Get refresh token only
     * 
     * @param string $resourceId Resource identifier
     * @return string|null Refresh token or null if not found
     */
    public function getRefreshToken(string $resourceId): ?string
    {
        try {
            $sql = "SELECT refresh_token FROM `{$this->defaultCollection}` WHERE resource_id = ? AND (client_id = ? OR client_id IS NULL)";
            $stmt = $this->client->prepare($sql);
            $stmt->execute([$resourceId, $this->clientId]);
            $row = $stmt->fetch();

            return $row ? $row['refresh_token'] : null;
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to get refresh token for {$resourceId}: " . $e->getMessage());
            return null;
        }
    }

    /**
     * Get all sessions for current application
     * 
     * @return SessionData[] Array of session data
     */
    public function getSessionsByApplication(): array
    {
        try {
            $sql = "SELECT * FROM `{$this->defaultCollection}` WHERE client_id = ?";
            $stmt = $this->client->prepare($sql);
            $stmt->execute([$this->clientId]);
            $rows = $stmt->fetchAll();

            $sessions = [];
            foreach ($rows as $row) {
                $sessionData = new SessionData();
                $sessionData->access_token = $row['access_token'];
                $sessionData->refresh_token = $row['refresh_token'];
                $sessionData->token_type = $row['token_type'];
                $sessionData->scope = $row['scope'];
                $sessionData->user_type = $row['user_type'];
                $sessionData->company_id = $row['company_id'];
                $sessionData->location_id = $row['location_id'];
                $sessionData->expire_at = $row['expire_at'];
                
                $sessions[] = $sessionData;
            }

            return $sessions;
            
        } catch (PDOException $e) {
            $this->logger->error("SqlStorage: Failed to get sessions by application: " . $e->getMessage());
            return [];
        }
    }
}