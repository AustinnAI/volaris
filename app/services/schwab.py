"""
Schwab API Client
Provides real-time 1-minute and 5-minute OHLC data via OAuth 2.0 PKCE.

Documentation: https://developer.schwab.com/products/trader-api--individual
"""

import base64
import hashlib
import secrets
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlencode

from app.config import settings
from app.services.base_client import BaseAPIClient
from app.services.exceptions import AuthenticationError, DataNotFoundError
from app.utils.cache import cache


class SchwabClient(BaseAPIClient):
    """
    Schwab API client for real-time market data.

    Features:
    - OAuth 2.0 PKCE authorization flow
    - Automatic token refresh
    - Real-time 1-minute and 5-minute price data
    - Quote data
    - Options chains
    - Market hours

    Note: Requires OAuth setup. Tokens are cached in Redis.
    """

    def __init__(self):
        if not settings.SCHWAB_APP_KEY or not settings.SCHWAB_SECRET_KEY:
            raise AuthenticationError(
                "Schwab API credentials not configured",
                provider="Schwab",
            )

        super().__init__(
            base_url=settings.SCHWAB_API_BASE,
            provider_name="Schwab",
            timeout=30.0,
        )

        self.app_key = settings.SCHWAB_APP_KEY
        self.secret_key = settings.SCHWAB_SECRET_KEY
        self.redirect_uri = settings.SCHWAB_REDIRECT_URI
        self.auth_base = "https://api.schwabapi.com/v1/oauth"

        # Token cache keys
        self.access_token_key = "schwab:access_token"
        self.refresh_token_key = "schwab:refresh_token"

    # ==================== OAuth 2.0 PKCE Flow ====================

    def generate_pkce_codes(self) -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        Returns:
            (code_verifier, code_challenge) tuple
        """
        # Generate code verifier (43-128 chars, base64url encoded)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")
        code_verifier = code_verifier.rstrip("=")

        # Generate code challenge (SHA256 hash of verifier)
        challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(challenge).decode("utf-8")
        code_challenge = code_challenge.rstrip("=")

        return code_verifier, code_challenge

    def get_authorization_url(self, include_state: bool = True) -> tuple[str, str]:
        """
        Generate OAuth authorization URL for user consent.

        Args:
            include_state: If True, includes code_verifier in state parameter

        Returns:
            (authorization_url, code_verifier) tuple

        Usage:
            1. Call this method to get the URL
            2. Store code_verifier securely (or pass in URL state)
            3. Redirect user to authorization_url
            4. User approves and is redirected to redirect_uri with code
            5. Use code and code_verifier to get tokens
        """
        code_verifier, code_challenge = self.generate_pkce_codes()

        params = {
            "response_type": "code",
            "client_id": self.app_key,
            "redirect_uri": self.redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        # Optionally include code_verifier in state parameter for callback
        if include_state:
            params["state"] = code_verifier

        auth_url = f"{self.auth_base}/authorize?{urlencode(params)}"
        return auth_url, code_verifier

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
        code_verifier: str,
    ) -> Dict[str, str]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            authorization_code: Code from OAuth callback
            code_verifier: PKCE code verifier from authorization step

        Returns:
            Token response dict with access_token, refresh_token, expires_in

        Example response:
            {
                "access_token": "...",
                "refresh_token": "...",
                "token_type": "Bearer",
                "expires_in": 1800,
                "scope": "..."
            }
        """
        endpoint = f"{self.auth_base}/token"

        # Basic auth header
        credentials = f"{self.app_key}:{self.secret_key}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }

        response = await self.client.post(endpoint, headers=headers, data=data)
        response.raise_for_status()
        tokens = response.json()

        # Cache tokens
        await self._cache_tokens(tokens)

        return tokens

    async def refresh_access_token(
        self,
        refresh_token: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Refresh the access token using refresh token.

        Args:
            refresh_token: Refresh token (or use cached one)

        Returns:
            New token response

        Raises:
            AuthenticationError if refresh fails
        """
        if not refresh_token:
            # Try to get from cache
            refresh_token = await cache.get(self.refresh_token_key)

            if not refresh_token and settings.SCHWAB_REFRESH_TOKEN:
                refresh_token = settings.SCHWAB_REFRESH_TOKEN

        if not refresh_token:
            raise AuthenticationError(
                "No refresh token available",
                provider="Schwab",
            )

        endpoint = f"{self.auth_base}/token"

        credentials = f"{self.app_key}:{self.secret_key}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = await self.client.post(endpoint, headers=headers, data=data)
            response.raise_for_status()
            tokens = response.json()

            # Cache new tokens
            await self._cache_tokens(tokens)

            return tokens

        except Exception as e:
            raise AuthenticationError(
                f"Token refresh failed: {str(e)}",
                provider="Schwab",
            ) from e

    async def _cache_tokens(self, tokens: Dict) -> None:
        """Cache access and refresh tokens with expiry tracking"""
        from datetime import datetime, timezone
        from app.utils.logger import app_logger

        if "access_token" in tokens:
            # Cache access token with TTL slightly less than expires_in
            ttl = tokens.get("expires_in", 1800) - 60  # 1 min buffer
            await cache.set(self.access_token_key, tokens["access_token"], ttl=ttl)

        if "refresh_token" in tokens:
            # Refresh tokens typically last 7 days
            refresh_ttl = 7 * 24 * 3600  # 7 days in seconds
            await cache.set(
                self.refresh_token_key,
                tokens["refresh_token"],
                ttl=refresh_ttl,
            )

            # Store timestamp when refresh token was issued
            token_issued_key = f"{self.refresh_token_key}:issued_at"
            await cache.set(
                token_issued_key,
                datetime.now(timezone.utc).isoformat(),
                ttl=refresh_ttl,
            )

            app_logger.info(
                "Schwab refresh token cached",
                extra={"expires_in_days": 7},
            )

    async def _get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary"""
        from datetime import datetime, timedelta, timezone
        from app.utils.logger import app_logger

        # Try cached token first
        access_token = await cache.get(self.access_token_key)

        if access_token:
            # Check if refresh token is nearing expiry
            await self._check_refresh_token_expiry()
            return access_token

        # Need to refresh
        tokens = await self.refresh_access_token()
        return tokens["access_token"]

    async def _check_refresh_token_expiry(self) -> None:
        """Log warning if refresh token is nearing expiry"""
        from datetime import datetime, timedelta, timezone
        from app.utils.logger import app_logger

        token_issued_key = f"{self.refresh_token_key}:issued_at"
        issued_at_str = await cache.get(token_issued_key)

        if not issued_at_str:
            # No timestamp tracked - likely using .env refresh token
            return

        try:
            issued_at = datetime.fromisoformat(issued_at_str)
            now = datetime.now(timezone.utc)
            age_days = (now - issued_at).days

            # Warn if token is 6+ days old (expires in 7 days)
            if age_days >= 6:
                app_logger.warning(
                    "Schwab refresh token nearing expiry",
                    extra={
                        "age_days": age_days,
                        "expires_in_days": 7 - age_days,
                        "action": "Regenerate token via /api/v1/auth/schwab/authorize",
                    },
                )
        except (ValueError, TypeError) as e:
            app_logger.debug(f"Could not parse refresh token timestamp: {e}")

    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with access token"""
        access_token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    # ==================== Market Data API ====================

    async def get_quote(self, symbol: str) -> Dict:
        """
        Get real-time quote for a symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL", "SPY")

        Returns:
            Quote data

        Example response:
            {
                "quote": {
                    "symbol": "AAPL",
                    "bidPrice": 185.55,
                    "askPrice": 185.57,
                    "lastPrice": 185.56,
                    "bidSize": 100,
                    "askSize": 100,
                    "lastSize": 50,
                    "highPrice": 186.40,
                    "lowPrice": 183.92,
                    "openPrice": 184.35,
                    "closePrice": 184.35,
                    "totalVolume": 50123456,
                    "quoteTime": 1610000000000,
                    "tradeTime": 1610000000000,
                    "52WeekHigh": 200.00,
                    "52WeekLow": 150.00
                }
            }
        """
        endpoint = f"/marketdata/v1/{symbol.upper()}/quotes"
        headers = await self._get_headers()
        return await self.get(endpoint, headers=headers)

    async def get_price_history(
        self,
        symbol: str,
        period_type: str = "day",
        period: int = 1,
        frequency_type: str = "minute",
        frequency: int = 1,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Get price history (candles).

        Args:
            symbol: Stock symbol
            period_type: Period type (day, month, year, ytd)
            period: Number of periods
            frequency_type: Frequency type (minute, daily, weekly, monthly)
            frequency: Frequency (1, 5, 10, 15, 30 for minute)
            start_date: Start datetime (epoch ms or datetime)
            end_date: End datetime (epoch ms or datetime)

        Returns:
            Candle data

        Example for 1-minute bars:
            period_type="day", period=1, frequency_type="minute", frequency=1

        Example for 5-minute bars:
            period_type="day", period=5, frequency_type="minute", frequency=5
        """
        endpoint = f"/marketdata/v1/pricehistory"

        params = {
            "symbol": symbol.upper(),
            "periodType": period_type,
            "period": period,
            "frequencyType": frequency_type,
            "frequency": frequency,
        }

        if start_date:
            params["startDate"] = (
                int(start_date.timestamp() * 1000)
                if isinstance(start_date, datetime)
                else start_date
            )

        if end_date:
            params["endDate"] = (
                int(end_date.timestamp() * 1000) if isinstance(end_date, datetime) else end_date
            )

        headers = await self._get_headers()
        return await self.get(endpoint, headers=headers, params=params)

    async def get_option_chain(
        self,
        symbol: str,
        contract_type: str = "ALL",
        strike_count: int = 10,
        include_quotes: bool = True,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Dict:
        """
        Get options chain for a symbol.

        Args:
            symbol: Underlying symbol
            contract_type: Contract type (CALL, PUT, ALL)
            strike_count: Number of strikes to return
            include_quotes: Include quote data
            from_date: From expiration date
            to_date: To expiration date

        Returns:
            Options chain data
        """
        endpoint = f"/marketdata/v1/chains"

        params = {
            "symbol": symbol.upper(),
            "contractType": contract_type,
            "strikeCount": strike_count,
            "includeQuotes": str(include_quotes).lower(),
        }

        if from_date:
            params["fromDate"] = from_date.isoformat()
        if to_date:
            params["toDate"] = to_date.isoformat()

        headers = await self._get_headers()
        return await self.get(endpoint, headers=headers, params=params)

    async def get_market_hours(
        self,
        markets: List[str],
        date: Optional[date] = None,
    ) -> Dict:
        """
        Get market hours for specified markets.

        Args:
            markets: List of markets (equity, option, bond, etc.)
            date: Date to check (default: today)

        Returns:
            Market hours data
        """
        endpoint = "/marketdata/v1/markets"

        params = {"markets": ",".join(markets)}
        if date:
            params["date"] = date.isoformat()

        headers = await self._get_headers()
        return await self.get(endpoint, headers=headers, params=params)

    async def health_check(self) -> bool:
        """Check if Schwab API is accessible and authenticated"""
        try:
            await self.get_quote("SPY")
            return True
        except Exception:
            return False


# Global client instance (only if credentials are configured)
schwab_client = SchwabClient() if (settings.SCHWAB_APP_KEY and settings.SCHWAB_SECRET_KEY) else None
