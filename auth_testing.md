# Paperbow authentication testing

1. POST `/api/auth/login` with the admin credentials in `/app/memory/test_credentials.md`.
2. Confirm the response returns the admin role and sets an httpOnly `access_token` cookie.
3. GET `/api/auth/me` with the cookie and confirm the same user is returned.
4. POST `/api/auth/logout`, then confirm `/api/auth/me` returns 401.
5. Confirm `/api/dashboard`, `/api/customers`, `/api/products`, and `/api/orders` return 401 without a session and 200 with a session.