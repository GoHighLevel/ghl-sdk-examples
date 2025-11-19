"""
SQL/MySQL implementation of SessionStorage for Python
Stores OAuth tokens and session data in MySQL database
"""

import pymysql
import time
from typing import Optional, Dict, Any, List
from highlevel.storage import SessionStorage, ISessionData
from highlevel.logging import Logger


class SqlStorage(SessionStorage):
    """
    SQL/MySQL implementation of SessionStorage
    Stores OAuth tokens and session data in MySQL database
    """

    def __init__(
        self,
        host: str = 'localhost',
        database: str = 'ghl_sessions',
        username: str = 'root',
        password: str = '',
        port: int = 3306,
        charset: str = 'utf8mb4',
        logger: Optional[Logger] = None
    ):
        """
        Create new SqlStorage instance

        Args:
            host: Database host
            database: Database name
            username: Database username
            password: Database password
            port: Database port
            charset: Database charset
            logger: Logger instance
        """
        super().__init__(logger)

        self.config = {
            'host': host,
            'database': database,
            'username': username,
            'password': password,
            'port': port,
            'charset': charset
        }

        self.client: Optional[pymysql.Connection] = None
        self.client_id: Optional[str] = None
        self.default_collection = 'ghl_sessions'

    def set_client_id(self, client_id: str) -> None:
        """Set the client ID"""
        self.client_id = client_id

    async def init(self) -> None:
        """
        Initialize database connection and create tables

        Raises:
            Exception: If connection fails
        """
        try:
            self.client = pymysql.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['username'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config['charset'],
                autocommit=True
            )

            self.logger.debug('SqlStorage: Database connection established')

            # Create default sessions table
            self.create_collection(self.default_collection)

        except pymysql.Error as e:
            self.logger.error(f'SqlStorage: Failed to connect to database: {e}')
            raise Exception(f'Failed to connect to database: {e}')

    async def disconnect(self) -> None:
        """Close database connection"""
        if self.client:
            self.client.close()
            self.client = None
        self.logger.debug('SqlStorage: Database connection closed')

    async def create_collection(self, collection_name: str) -> None:
        """
        Create sessions table if it doesn't exist

        Args:
            collection_name: Table name

        Raises:
            Exception: If table creation fails
        """
        try:
            with self.client.cursor() as cursor:
                sql = f"""
                    CREATE TABLE IF NOT EXISTS `{collection_name}` (
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
                """

                cursor.execute(sql)
                self.logger.debug(f"SqlStorage: Table '{collection_name}' created or verified")

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to create table '{collection_name}': {e}")
            raise Exception(f"Failed to create table '{collection_name}': {e}")

    def get_collection(self, collection_name: str) -> str:
        """Get table reference (returns table name for SQL)"""
        return collection_name

    async def set_session(self, resource_id: str, session_data: ISessionData) -> None:
        """
        Store session data

        Args:
            resource_id: Resource identifier
            session_data: Session data to store

        Raises:
            Exception: If storage fails
        """
        try:
            expire_at = None
            if session_data.get('expires_in'):
                expire_at = self._calculate_expire_at(session_data.get('expires_in'))

            with self.client.cursor() as cursor:
                sql = f"""
                    INSERT INTO `{self.default_collection}` (
                        resource_id, client_id, access_token, refresh_token, token_type,
                        scope, user_type, company_id, location_id, expire_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                """

                cursor.execute(sql, [
                    resource_id,
                    self.client_id,
                    session_data.get('access_token'),
                    session_data.get('refresh_token'),
                    session_data.get('token_type'),
                    session_data.get('scope'),
                    session_data.get('userType'),
                    session_data.get('companyId'),
                    session_data.get('locationId'),
                    expire_at
                ])

            self.logger.debug(f"SqlStorage: Session stored for resource ID: {resource_id}")

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to store session for {resource_id}: {e}")
            raise Exception(f"Failed to store session: {e}")

    async def get_session(self, resource_id: str) -> Optional[ISessionData]:
        """
        Retrieve session data

        Args:
            resource_id: Resource identifier

        Returns:
            Session data or None if not found
        """
        try:
            with self.client.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = f"SELECT * FROM `{self.default_collection}` WHERE resource_id = %s AND (client_id = %s OR client_id IS NULL)"
                cursor.execute(sql, [resource_id, self.client_id])
                row = cursor.fetchone()

                if not row:
                    self.logger.debug(f"SqlStorage: No session found for resource ID: {resource_id}")
                    return None

                session_data = ISessionData(
                    access_token=row.get('access_token'),
                    refresh_token=row.get('refresh_token'),
                    token_type=row.get('token_type'),
                    scope=row.get('scope'),
                    userType=row.get('user_type'),
                    companyId=row.get('company_id'),
                    locationId=row.get('location_id')
                )
                session_data.expire_at = row.get('expire_at')

                self.logger.debug(f"SqlStorage: Session retrieved for resource ID: {resource_id}")
                return session_data

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to retrieve session for {resource_id}: {e}")
            return None

    async def delete_session(self, resource_id: str) -> None:
        """
        Delete session data

        Args:
            resource_id: Resource identifier
        """
        try:
            with self.client.cursor() as cursor:
                sql = f"DELETE FROM `{self.default_collection}` WHERE resource_id = %s AND (client_id = %s OR client_id IS NULL)"
                cursor.execute(sql, [resource_id, self.client_id])

            self.logger.debug(f"SqlStorage: Session deleted for resource ID: {resource_id}")

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to delete session for {resource_id}: {e}")

    async def get_access_token(self, resource_id: str) -> Optional[str]:
        """
        Get access token only

        Args:
            resource_id: Resource identifier

        Returns:
            Access token or None if not found
        """
        try:
            with self.client.cursor() as cursor:
                sql = f"SELECT access_token FROM `{self.default_collection}` WHERE resource_id = %s AND (client_id = %s OR client_id IS NULL)"
                cursor.execute(sql, [resource_id, self.client_id])
                row = cursor.fetchone()

                return row[0] if row else None

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to get access token for {resource_id}: {e}")
            return None

    async def get_refresh_token(self, resource_id: str) -> Optional[str]:
        """
        Get refresh token only

        Args:
            resource_id: Resource identifier

        Returns:
            Refresh token or None if not found
        """
        try:
            with self.client.cursor() as cursor:
                sql = f"SELECT refresh_token FROM `{self.default_collection}` WHERE resource_id = %s AND (client_id = %s OR client_id IS NULL)"
                cursor.execute(sql, [resource_id, self.client_id])
                row = cursor.fetchone()

                return row[0] if row else None

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to get refresh token for {resource_id}: {e}")
            return None

    async def get_sessions_by_application(self) -> List[ISessionData]:
        """
        Get all sessions for current application

        Returns:
            List of session data
        """
        try:
            with self.client.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = f"SELECT * FROM `{self.default_collection}` WHERE client_id = %s"
                cursor.execute(sql, [self.client_id])
                rows = cursor.fetchall()

                sessions = []
                for row in rows:
                    session_data = ISessionData(
                        access_token=row.get('access_token'),
                        refresh_token=row.get('refresh_token'),
                        token_type=row.get('token_type'),
                        scope=row.get('scope'),
                        user_type=row.get('user_type'),
                        company_id=row.get('company_id'),
                        location_id=row.get('location_id')
                    )
                    session_data.expire_at = row.get('expire_at')
                    sessions.append(session_data)

                return sessions

        except pymysql.Error as e:
            self.logger.error(f"SqlStorage: Failed to get sessions by application: {e}")
            return []

    def _calculate_expire_at(self, expires_in: int) -> int:
        """Calculate expiration timestamp"""
        return int(time.time() * 1000) + (expires_in * 1000)
