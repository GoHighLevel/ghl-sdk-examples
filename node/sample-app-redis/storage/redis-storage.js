const { SessionStorage } = require('@ghl/api-client');
const Redis = require('redis');

/**
 * Redis-based session storage implementation for GHL SDK
 * Extends the base SessionStorage class and implements all required methods
 */
class RedisStorage extends SessionStorage {
  constructor(options = {}) {
    super();
    
    this.options = {
      host: options.host || process.env.REDIS_HOST || 'localhost',
      port: options.port || process.env.REDIS_PORT || 6379,
      password: options.password || process.env.REDIS_PASSWORD,
      db: options.db || process.env.REDIS_DB || 0,
      keyPrefix: options.keyPrefix || 'ghl:session:',
      ttl: options.ttl || 86400, // 24 hours default TTL
      ...options
    };
    
    this.client = null;
    this.clientId = null;
    this.isConnected = false;
  }

  /**
   * Initialize Redis connection
   */
  async init() {
    try {
      // Create Redis client
      this.client = Redis.createClient({
        socket: {
          host: this.options.host,
          port: this.options.port
        },
        password: this.options.password,
        database: this.options.db
      });

      // Handle connection events
      this.client.on('connect', () => {
        console.log('[RedisStorage] Connected to Redis');
        this.isConnected = true;
      });

      this.client.on('error', (error) => {
        console.error('[RedisStorage] Redis connection error:', error);
        this.isConnected = false;
      });

      this.client.on('end', () => {
        console.log('[RedisStorage] Redis connection closed');
        this.isConnected = false;
      });

      // Connect to Redis
      await this.client.connect();
      
      console.log('[RedisStorage] Redis storage initialized successfully');
    } catch (error) {
      console.error('[RedisStorage] Failed to initialize Redis storage:', error);
      throw error;
    }
  }

  /**
   * Set client ID for session management
   * @param {string} clientId - OAuth client ID
   */
  setClientId(clientId) {
    this.clientId = clientId;
    console.log('[RedisStorage] Client ID set:', clientId);
  }

  /**
   * Store session data in Redis
   * @param {string} resourceId - Resource identifier (companyId or locationId)
   * @param {object} sessionData - Session data to store
   */
  async setSession(resourceId, sessionData) {
    if (!this.isConnected || !this.client) {
      throw new Error('Redis client not initialized or connected');
    }

    try {
      const key = this.getSessionKey(resourceId);
      
      // Add metadata
      const dataToStore = {
        ...sessionData,
        resourceId,
        clientId: this.clientId,
        createdAt: Date.now(),
        updatedAt: Date.now()
      };

      // Store with TTL
      await this.client.setEx(
        key, 
        this.options.ttl, 
        JSON.stringify(dataToStore)
      );

      console.log(`[RedisStorage] Session stored for resource: ${resourceId}`);
    } catch (error) {
      console.error(`[RedisStorage] Failed to store session for ${resourceId}:`, error);
      throw error;
    }
  }

  /**
   * Retrieve session data from Redis
   * @param {string} resourceId - Resource identifier
   * @returns {object|null} Session data or null if not found
   */
  async getSession(resourceId) {
    if (!this.isConnected || !this.client) {
      throw new Error('Redis client not initialized or connected');
    }

    try {
      const key = this.getSessionKey(resourceId);
      const data = await this.client.get(key);
      
      if (!data) {
        console.log(`[RedisStorage] No session found for resource: ${resourceId}`);
        return null;
      }

      const sessionData = JSON.parse(data);
      console.log(`[RedisStorage] Session retrieved for resource: ${resourceId}`);
      return sessionData;
    } catch (error) {
      console.error(`[RedisStorage] Failed to retrieve session for ${resourceId}:`, error);
      throw error;
    }
  }

  /**
   * Get access token for a specific resource
   * @param {string} resourceId - Resource identifier
   * @returns {string|null} Access token or null if not found
   */
  async getAccessToken(resourceId) {
    try {
      const sessionData = await this.getSession(resourceId);
      return sessionData?.access_token || null;
    } catch (error) {
      console.error(`[RedisStorage] Failed to get access token for ${resourceId}:`, error);
      return null;
    }
  }

  /**
   * Get refresh token for a specific resource
   * @param {string} resourceId - Resource identifier
   * @returns {string|null} Refresh token or null if not found
   */
  async getRefreshToken(resourceId) {
    try {
      const sessionData = await this.getSession(resourceId);
      return sessionData?.refresh_token || null;
    } catch (error) {
      console.error(`[RedisStorage] Failed to get refresh token for ${resourceId}:`, error);
      return null;
    }
  }



  /**
   * Disconnect from Redis
   */
  async disconnect() {
    try {
      if (this.client && this.isConnected) {
        await this.client.quit();
        console.log('[RedisStorage] Disconnected from Redis');
      }
    } catch (error) {
      console.error('[RedisStorage] Error during disconnect:', error);
      throw error;
    }
  }

  /**
   * Generate Redis key for session storage
   * @param {string} resourceId - Resource identifier
   * @returns {string} Redis key
   */
  getSessionKey(resourceId) {
    return `${this.options.keyPrefix}${resourceId}`;
  }
}

module.exports = RedisStorage;
