"""
OAuth Authentication Endpoints
Handles OAuth callbacks for providers requiring authorization.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional

from app.services.schwab import schwab_client
from app.utils.logger import app_logger

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/schwab/callback")
async def schwab_oauth_callback(
    code: str = Query(..., description="Authorization code from Schwab"),
    code_verifier: Optional[str] = Query(None, description="PKCE code verifier"),
):
    """
    Schwab OAuth callback endpoint.

    This endpoint is called by Schwab after user authorization.

    Flow:
    1. User clicks authorization URL
    2. Schwab redirects here with code
    3. We exchange code for tokens
    4. Tokens are cached in Redis

    Args:
        code: Authorization code from Schwab
        code_verifier: PKCE code verifier (if provided in state)

    Returns:
        HTML page with success/failure message
    """
    try:
        if not code_verifier:
            # If code_verifier not in URL, need to retrieve from session/cache
            # For now, return error - user must provide verifier
            return HTMLResponse(
                content="""
                <html>
                <head><title>Schwab OAuth - Error</title></head>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1 style="color: #d32f2f;">❌ Error</h1>
                    <p>Code verifier not found. Please use the authorization flow with code_verifier.</p>
                    <p>See documentation for proper OAuth setup.</p>
                </body>
                </html>
                """,
                status_code=400,
            )

        # Exchange code for tokens
        app_logger.info("Exchanging Schwab authorization code for tokens")
        tokens = await schwab_client.exchange_code_for_tokens(
            authorization_code=code,
            code_verifier=code_verifier,
        )

        app_logger.info("Successfully obtained Schwab tokens")

        # Return success page with refresh token
        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>Schwab OAuth - Success</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        padding: 40px;
                        max-width: 800px;
                        margin: 0 auto;
                    }}
                    .success {{ color: #2e7d32; }}
                    .token-box {{
                        background: #f5f5f5;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        word-break: break-all;
                        font-family: monospace;
                    }}
                    .warning {{
                        background: #fff3e0;
                        padding: 15px;
                        border-left: 4px solid #ff9800;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <h1 class="success">✅ Schwab OAuth Success!</h1>

                <p>Your Schwab account has been successfully authorized.</p>

                <h2>Refresh Token</h2>
                <p>Save this refresh token to your <code>.env</code> file:</p>
                <div class="token-box">
                    SCHWAB_REFRESH_TOKEN={tokens['refresh_token']}
                </div>

                <div class="warning">
                    <strong>⚠️ Important:</strong>
                    <ul>
                        <li>Add the refresh token to your <code>.env</code> file</li>
                        <li>Restart the application</li>
                        <li>The access token will be automatically refreshed as needed</li>
                        <li>Refresh tokens typically last 7 days</li>
                    </ul>
                </div>

                <h2>Token Details</h2>
                <ul>
                    <li>Access token expires in: {tokens.get('expires_in', 'N/A')} seconds</li>
                    <li>Token type: {tokens.get('token_type', 'Bearer')}</li>
                    <li>Tokens cached in Redis: ✓</li>
                </ul>

                <p><a href="/">← Back to Home</a></p>
            </body>
            </html>
            """,
            status_code=200,
        )

    except Exception as e:
        app_logger.error(f"Schwab OAuth callback error: {str(e)}")
        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Schwab OAuth - Error</title></head>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1 style="color: #d32f2f;">❌ OAuth Error</h1>
                <p>Failed to exchange authorization code for tokens.</p>
                <p style="color: #666;">Error: {str(e)}</p>
                <p><a href="/">← Back to Home</a></p>
            </body>
            </html>
            """,
            status_code=500,
        )


@router.get("/schwab/authorize")
async def schwab_authorize():
    """
    Generate Schwab authorization URL.

    Returns:
        HTML page with authorization URL and instructions
    """
    try:
        auth_url, code_verifier = schwab_client.get_authorization_url()

        return HTMLResponse(
            content=f"""
            <html>
            <head>
                <title>Schwab OAuth - Authorize</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        padding: 40px;
                        max-width: 800px;
                        margin: 0 auto;
                    }}
                    .code-box {{
                        background: #f5f5f5;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        word-break: break-all;
                        font-family: monospace;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 24px;
                        background: #1976d2;
                        color: white;
                        text-decoration: none;
                        border-radius: 4px;
                        margin: 20px 0;
                    }}
                    .warning {{
                        background: #fff3e0;
                        padding: 15px;
                        border-left: 4px solid #ff9800;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <h1>🔐 Schwab OAuth Authorization</h1>

                <p>To authorize Volaris to access your Schwab account, follow these steps:</p>

                <h2>Step 1: Save Code Verifier</h2>
                <p>Copy and save this code verifier (you'll need it later):</p>
                <div class="code-box">{code_verifier}</div>

                <h2>Step 2: Authorize</h2>
                <p>Click the button below to authorize with Schwab:</p>
                <a href="{auth_url}&state={code_verifier}" class="button" target="_blank">
                    Authorize with Schwab →
                </a>

                <div class="warning">
                    <strong>⚠️ Important:</strong>
                    <ul>
                        <li>The code_verifier is included in the authorization URL state parameter</li>
                        <li>After authorizing, you'll be redirected to the callback endpoint</li>
                        <li>The callback will display your refresh token</li>
                        <li>Add the refresh token to your <code>.env</code> file</li>
                    </ul>
                </div>

                <h2>Manual Authorization (Alternative)</h2>
                <p>If the button doesn't work, copy this URL:</p>
                <div class="code-box">{auth_url}&state={code_verifier}</div>

                <p><a href="/">← Back to Home</a></p>
            </body>
            </html>
            """,
            status_code=200,
        )

    except Exception as e:
        app_logger.error(f"Error generating Schwab auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
