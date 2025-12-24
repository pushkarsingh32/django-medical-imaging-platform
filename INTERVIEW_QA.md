# Django + Next.js Authentication - Interview Q&A Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture & Design](#architecture--design)
3. [Backend (Django) Questions](#backend-django-questions)
4. [Frontend (Next.js) Questions](#frontend-nextjs-questions)
5. [Security & Best Practices](#security--best-practices)
6. [Authentication Flow](#authentication-flow)
7. [Technical Deep Dive](#technical-deep-dive)
8. [Troubleshooting & Debugging](#troubleshooting--debugging)
9. [Deployment & Production](#deployment--production)

---

## Project Overview

### Q1: What did you build in this project?
**A:** I built a fullstack authentication system using Django for the backend and Next.js for the frontend. The system provides:
- User registration with email/password
- Email verification
- Login/Logout functionality
- Password reset flow
- Session management using tokens
- Protected routes on the frontend

It's a production-ready authentication system that can handle 130+ OAuth providers, two-factor authentication, and follows industry best practices.

### Q2: Why did you choose Django + Next.js?
**A:**
- **Django**: Mature, secure, batteries-included framework with excellent ORM and admin interface. Perfect for building robust APIs.
- **Next.js**: Modern React framework with server-side rendering, great developer experience, and built-in routing.
- **Separation of concerns**: Backend handles business logic and data, frontend handles UI/UX.
- **Scalability**: Can deploy independently, scale horizontally, and use CDN for frontend.

### Q3: What is django-allauth and why use it?
**A:** Django-allauth is a comprehensive authentication package for Django that provides:
- Email/password authentication
- 130+ social OAuth providers (Google, GitHub, Microsoft, etc.)
- Email verification
- Password reset
- Multi-factor authentication (TOTP, WebAuthn)
- Headless API mode for SPAs

I chose the **headless mode** which provides a REST API that my Next.js frontend can consume, making it framework-agnostic and perfect for modern frontend frameworks.

---

## Architecture & Design

### Q4: Explain the overall architecture of your authentication system
**A:**

```
┌─────────────────────────────────────────┐
│         Next.js Frontend (Port 3000)    │
│  ┌────────────────────────────────┐    │
│  │  UI Components (Login, Signup)  │    │
│  │  AuthContext (React Context)    │    │
│  │  Custom Hooks (useAuth)         │    │
│  └────────────────────────────────┘    │
└─────────────┬───────────────────────────┘
              │ HTTP Requests (X-Session-Token)
              │
┌─────────────▼───────────────────────────┐
│      Django Backend (Port 8000)          │
│  ┌────────────────────────────────┐    │
│  │  django-allauth Headless API    │    │
│  │  REST Framework                 │    │
│  │  Custom Middleware (CSRF)       │    │
│  └────────────────────────────────┘    │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│         MySQL Database                   │
│  - Users                                 │
│  - Email addresses                       │
│  - Sessions                              │
│  - MFA authenticators                    │
└──────────────────────────────────────────┘
```

**Key Points:**
- **Stateless API**: Backend is a pure API, no templates
- **Token-based auth**: Uses session tokens (X-Session-Token header)
- **CORS enabled**: Allows cross-origin requests from Next.js
- **Modular frontend**: Separate API client, context, and UI components

### Q5: How did you structure your frontend code?
**A:** I used a **modular architecture** with separation of concerns:

```
frontend/
├── app/                    # Next.js App Router
│   ├── auth/              # Authentication pages
│   │   ├── login/
│   │   ├── signup/
│   │   └── verify-email/
│   └── dashboard/         # Protected routes
├── contexts/
│   └── AuthContext.tsx    # Global auth state
├── lib/
│   └── allauth.ts         # Modular API client
└── .env.local             # Environment variables
```

**API Client Structure (DRY & Modular):**
```typescript
class AllauthAPI {
  auth: AuthModule;        // login, signup, logout
  email: EmailModule;      // verification
  password: PasswordModule; // reset, change
  mfa: MFAModule;          // 2FA, TOTP
}
```

### Q6: What design patterns did you use?
**A:**
1. **Module Pattern**: Separated API client into modules (auth, email, password, MFA)
2. **Singleton Pattern**: Single instance of AllauthAPI exported
3. **Context Pattern**: React Context for global auth state
4. **Custom Hooks**: `useAuth()` hook for component-level access
5. **Storage Helper Pattern**: Abstracted localStorage operations
6. **Middleware Pattern**: Custom Django middleware for CSRF exemption

---

## Backend (Django) Questions

### Q7: How does django-allauth headless work?
**A:** Django-allauth headless provides a **REST API** instead of traditional Django views:

**Traditional Django-allauth:**
- Returns HTML templates
- Uses Django sessions and cookies
- Coupled to Django frontend

**Headless Mode:**
- Returns JSON responses
- Uses session tokens (X-Session-Token header)
- Framework-agnostic (works with React, Vue, mobile apps)
- Provides OpenAPI specification

**Key Setting:**
```python
HEADLESS_ONLY = True  # Disables HTML views, API only
```

### Q8: What is the session token strategy?
**A:**
```python
HEADLESS_TOKEN_STRATEGY = 'allauth.headless.tokens.sessions.SessionTokenStrategy'
```

This uses **session-based tokens**:
- Token generated on login
- Stored in database (hashed)
- Sent to client in response
- Client includes in `X-Session-Token` header
- Server validates against database

**Alternative:** JWT strategy (stateless tokens)

### Q9: How did you handle CORS?
**A:** Configured CORS to allow Next.js frontend:

```python
# Installed django-cors-headers
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Before CommonMiddleware
    ...
]

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
CORS_ALLOW_CREDENTIALS = True  # Allow cookies/tokens
CORS_ALLOW_HEADERS = [
    'x-session-token',  # Custom header for allauth
    ...
]
```

### Q10: Why did you create custom middleware for CSRF?
**A:** Django's CSRF protection blocks API requests by default. Since django-allauth headless uses **session tokens** (not CSRF tokens), I created middleware to exempt allauth endpoints:

```python
class DisableCSRFForAllauthMiddleware:
    def __call__(self, request):
        if request.path.startswith('/_allauth/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return self.get_response(request)
```

**Why this is safe:**
- Allauth validates the `X-Session-Token` header
- Session tokens provide authentication
- CSRF tokens are redundant for token-based auth
- CORS headers already restrict origins

### Q11: How is the database structured?
**A:** Django-allauth creates these tables:

```sql
-- Core tables
auth_user                  -- Django's built-in user table
account_emailaddress       -- User email addresses
account_emailconfirmation  -- Email verification tokens

-- Social auth
socialaccount_socialaccount  -- Social login accounts
socialaccount_socialapp      -- OAuth app credentials
socialaccount_socialtoken    -- OAuth tokens

-- MFA
mfa_authenticator          -- TOTP/WebAuthn authenticators
usersessions_usersession   -- Track active sessions
```

### Q12: What are the main API endpoints?
**A:**
Base URL: `http://localhost:8000/_allauth/browser/v1/`

```
POST   /auth/signup          - Register new user
POST   /auth/login           - Login user
GET    /auth/session         - Get current session
DELETE /auth/session         - Logout
POST   /auth/email/verify    - Verify email
POST   /auth/password/reset  - Request password reset
GET    /auth/providers       - List OAuth providers
POST   /mfa/authenticators/totp - Activate TOTP 2FA
```

Full API docs at: `http://localhost:8000/_allauth/openapi.html`

---

## Frontend (Next.js) Questions

### Q13: How does the Auth Context work?
**A:**

```typescript
// contexts/AuthContext.tsx
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize: Check if user has valid session
  useEffect(() => {
    allauth.initialize();  // Load token from localStorage
    refreshSession();      // Validate with backend
  }, []);

  const login = async (email, password) => {
    const response = await allauth.auth.login(email, password);
    setUser(response.data.user);  // Update global state
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, ... }}>
      {children}
    </AuthContext.Provider>
  );
}
```

**Benefits:**
- Global auth state accessible anywhere
- Single source of truth
- Automatic session persistence
- Clean component APIs via `useAuth()` hook

### Q14: How do you protect routes in Next.js?
**A:** Using the auth context in components:

```typescript
// app/dashboard/page.tsx
export default function DashboardPage() {
  const { user, isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isLoading, isAuthenticated]);

  if (isLoading) return <LoadingSpinner />;
  if (!isAuthenticated) return null;

  return <Dashboard user={user} />;
}
```

**Better approach** (using middleware.ts):
```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  const sessionToken = request.cookies.get('session_token');

  if (request.nextUrl.pathname.startsWith('/dashboard') && !sessionToken) {
    return NextResponse.redirect(new URL('/auth/login', request.url));
  }
}
```

### Q15: How does the modular API client work?
**A:**

```typescript
// lib/allauth.ts

// 1. HTTP Client (handles all requests)
class HttpClient {
  async request(endpoint, method, body) {
    const headers = { 'X-Session-Token': this.getToken() };
    const response = await fetch(API_BASE + endpoint, {
      method, headers, body, credentials: 'include'
    });
    return response.json();
  }
}

// 2. Modules (group related functionality)
class AuthModule {
  constructor(private client: HttpClient) {}

  login(email, password) {
    return this.client.request('/auth/login', 'POST', { email, password });
  }

  signup(email, password) {
    return this.client.request('/auth/signup', 'POST', { email, password });
  }
}

// 3. Main API class (composes modules)
class AllauthAPI {
  private client = new HttpClient();

  auth = new AuthModule(this.client);
  email = new EmailModule(this.client);
  password = new PasswordModule(this.client);
  mfa = new MFAModule(this.client);
}

// 4. Export singleton
export const allauth = new AllauthAPI();
```

**Benefits:**
- **DRY**: No code duplication
- **Modular**: Easy to add new features
- **Type-safe**: TypeScript interfaces
- **Testable**: Each module can be tested independently
- **Clean API**: `allauth.auth.login()` vs messy fetch calls

### Q16: How is session persistence handled?
**A:**

```typescript
// On login/signup
const response = await allauth.auth.login(email, password);
if (response.meta?.session_token) {
  // Save to localStorage
  localStorage.setItem('session_token', response.meta.session_token);
}

// On app load
allauth.initialize();  // Reads from localStorage

// On every request
headers['X-Session-Token'] = localStorage.getItem('session_token');

// On logout
localStorage.removeItem('session_token');
```

**Why localStorage?**
- Persists across page refreshes
- Accessible in client-side JavaScript
- Simple API

**Alternative:** httpOnly cookies (more secure, prevents XSS)

---

## Security & Best Practices

### Q17: What security measures did you implement?
**A:**

1. **Token-based authentication**: Session tokens instead of passwords in every request
2. **HTTPS only (production)**: Secure cookie flags
3. **CORS restrictions**: Only localhost:3000 allowed
4. **Password hashing**: Django's PBKDF2 algorithm
5. **Email verification**: Optional/mandatory email confirmation
6. **Token expiration**: Tokens expire after inactivity
7. **CSRF protection**: Custom middleware for API
8. **SQL injection prevention**: Django ORM parameterized queries
9. **XSS prevention**: React auto-escapes output
10. **Rate limiting**: Django-allauth built-in rate limiting

### Q18: How do you prevent common vulnerabilities?

**SQL Injection:**
```python
# Django ORM prevents SQL injection
User.objects.filter(email=email)  # Safe: parameterized query
```

**XSS (Cross-Site Scripting):**
```typescript
// React automatically escapes
<div>{user.email}</div>  // Safe: auto-escaped
```

**CSRF (Cross-Site Request Forgery):**
```python
# Session tokens + CORS prevent CSRF
# Each request requires valid X-Session-Token
# CORS only allows requests from localhost:3000
```

**Brute Force:**
```python
# Django-allauth has built-in rate limiting
# Can add django-ratelimit for custom limits
```

### Q19: How would you store sensitive data?
**A:**

**Never in code:**
```python
# ❌ Bad
SECRET_KEY = 'hardcoded-secret-123'

# ✅ Good
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
```

**Environment variables:**
```bash
# .env (not in git)
DJANGO_SECRET_KEY=your-secret-key
DATABASE_PASSWORD=your-db-password
```

**Production secrets:**
- Use AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault
- Never commit .env to git
- Rotate secrets regularly

### Q20: How do you handle password reset securely?
**A:**

1. **User requests reset**: Enters email
2. **Backend generates token**: Time-limited, one-time use
3. **Email sent**: Contains link with token
4. **User clicks link**: Frontend captures token from URL
5. **New password submitted**: Backend validates token
6. **Token invalidated**: Can't be reused
7. **Email notification**: User informed of password change

```python
# Django-allauth handles this automatically
# Tokens expire after 3 days by default
```

---

## Authentication Flow

### Q21: Walk me through the complete signup flow
**A:**

```
USER ACTION                 FRONTEND                    BACKEND                   DATABASE
─────────────────────────────────────────────────────────────────────────────────────────
1. Enter email/password
                    →
2.                          POST /auth/signup
                            { email, password }
                                                    →
3.                                                  Validate input
                                                    Hash password
                                                    Create user
                                                                              →
4.                                                                            INSERT user
                                                                              INSERT email
                                                                              ←
5.                                                  Generate session token
                                                    Generate verification key
                                                    Send verification email
                                                    ←
6.                          Response:
                            {
                              user: {...},
                              meta: {
                                session_token: "abc123"
                              }
                            }
                            ←
7. Save token to localStorage
   Update AuthContext
   Redirect to dashboard
```

### Q22: How does login work?
**A:**

```typescript
// Frontend
const login = async (email, password) => {
  // 1. Send credentials
  const response = await allauth.auth.login(email, password);

  // 2. Receive session token
  const token = response.meta.session_token;

  // 3. Store token
  localStorage.setItem('session_token', token);

  // 4. Update global state
  setUser(response.data.user);

  // 5. Redirect
  router.push('/dashboard');
};
```

**Backend validates:**
- Email exists
- Password matches (hashed comparison)
- Account is active
- Email verified (if required)

**Returns:**
- User object
- Session token
- Token expiry

### Q23: How does session validation work?
**A:**

```
EVERY REQUEST TO PROTECTED ENDPOINT:

Frontend                          Backend                    Database
────────────────────────────────────────────────────────────────────
1. GET /api/data/
   Headers: {
     X-Session-Token: "abc123"
   }
                              →
2.                                Extract token from header
                                  Hash token
                                                          →
3.                                                        SELECT session
                                                          WHERE token_hash
                                                          ←
4.                                Check if expired
                                  Check if valid
                                  Get user_id
                                                          →
5.                                                        SELECT user
                                                          ←
6.                                Attach user to request
                                  Process request
                                  ←
7. Response with data
```

### Q24: What happens when a token expires?
**A:**

```
1. User makes request with expired token
2. Backend validates token → EXPIRED
3. Backend returns 401 Unauthorized
4. Frontend receives 401
5. AuthContext clears state
6. User redirected to login
7. localStorage cleared
```

**Improvement with token refresh:**
```typescript
// Intercept 401 responses
if (response.status === 401) {
  // Try to refresh token
  const refreshed = await refreshToken();
  if (refreshed) {
    // Retry original request
  } else {
    // Redirect to login
  }
}
```

---

## Technical Deep Dive

### Q25: How does email verification work technically?
**A:**

```python
# Backend generates verification key
key = EmailConfirmationHMAC(email_address).key
# Example: "MQ:1vXysk:YV0RAj4hIEyOs4iVlWrI8nnI-2b2_FOIJe8dayY5YG8"

# Email sent with link
link = f"http://localhost:3000/auth/verify-email/{key}"

# User clicks link
# Frontend extracts key from URL params
const key = params.key;

// Frontend sends to backend
await allauth.email.verify(key);

# Backend validates
- Decodes HMAC
- Checks expiration
- Verifies signature
- Marks email as verified
```

**Key structure:**
```
MQ:1vXysk:YV0RAj4hIEyOs4iVlWrI8nnI-2b2_FOIJe8dayY5YG8
│  │      │
│  │      └─ HMAC signature
│  └─ Timestamp
└─ Email ID (base64)
```

### Q26: How would you add Google OAuth?
**A:**

**Backend:**
```python
# 1. Install provider
INSTALLED_APPS = [
    'allauth.socialaccount.providers.google',
]

# 2. Configure in Django admin
# Site: localhost:8000
# Provider: Google
# Client ID: from Google Cloud Console
# Secret: from Google Cloud Console
# Redirect URI: http://localhost:8000/accounts/google/login/callback/
```

**Frontend:**
```typescript
// 1. Get Google auth URL
const response = await allauth.auth.redirectToProvider('google', callbackUrl);

// 2. Redirect user to Google
window.location.href = response.data.url;

// 3. Google redirects back with code
// 4. Backend exchanges code for token
// 5. User logged in
```

### Q27: How does the middleware stack work?
**A:**

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',          # 1. Security headers
    'corsheaders.middleware.CorsMiddleware',                  # 2. CORS (before Common)
    'django.contrib.sessions.middleware.SessionMiddleware',   # 3. Session handling
    'django.middleware.common.CommonMiddleware',              # 4. Common processing
    'firstproject.middleware.DisableCSRFForAllauthMiddleware', # 5. CSRF exemption
    'django.middleware.csrf.CsrfViewMiddleware',              # 6. CSRF validation
    'django.contrib.auth.middleware.AuthenticationMiddleware', # 7. Auth
    'allauth.account.middleware.AccountMiddleware',           # 8. Allauth
    'django.contrib.messages.middleware.MessageMiddleware',   # 9. Messages
    'django.middleware.clickjacking.XFrameOptionsMiddleware', # 10. X-Frame
]
```

**Request flow:**
```
Request → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → View
Response ← 1 ← 2 ← 3 ← 4 ← 5 ← 6 ← 7 ← 8 ← 9 ← 10 ← View
```

**Order matters!**
- CORS before Common (process OPTIONS requests)
- Custom CSRF before CsrfView (exempt allauth)
- Auth after CSRF (need authenticated user)

### Q28: Explain the virtual environment setup
**A:**

**Why virtual environment?**
- Isolates project dependencies
- Prevents version conflicts
- Reproducible environments
- Easy to share (requirements.txt)

**Setup:**
```bash
# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate

# Install packages
pip install -r requirements.txt

# Freeze dependencies
pip freeze > requirements.txt
```

**Benefits:**
- Project A can use Django 5.2, Project B can use Django 4.2
- Clean system Python
- Easy deployment

---

## Troubleshooting & Debugging

### Q29: How would you debug a 403 CSRF error?
**A:**

**Steps:**
1. Check CORS configuration
2. Verify CSRF_TRUSTED_ORIGINS
3. Check middleware order
4. Inspect request headers
5. Check custom CSRF middleware

**Example debug:**
```python
# Add logging to middleware
class DisableCSRFForAllauthMiddleware:
    def __call__(self, request):
        print(f"Path: {request.path}")
        print(f"Headers: {request.headers}")

        if request.path.startswith('/_allauth/'):
            print("Exempting from CSRF")
            setattr(request, '_dont_enforce_csrf_checks', True)

        return self.get_response(request)
```

### Q30: How do you debug authentication issues?
**A:**

**Frontend debugging:**
```typescript
// Check token
console.log('Session token:', localStorage.getItem('session_token'));

// Check API calls
await allauth.auth.getSession().then(
  res => console.log('Session valid:', res),
  err => console.error('Session invalid:', err)
);

// Network tab
// Check X-Session-Token header in requests
```

**Backend debugging:**
```python
# Django shell
python manage.py shell

# Check user
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(email='test@example.com')
print(user.is_active)
print(user.emailaddress_set.all())

# Check sessions
from allauth.headless.tokens.sessions import SessionTokenStrategy
# Inspect active sessions
```

### Q31: Common errors and solutions?
**A:**

**Error: CORS policy blocked**
```
Solution: Add origin to CORS_ALLOWED_ORIGINS
```

**Error: 401 Unauthorized**
```
Solution: Check session token validity, may be expired
```

**Error: 403 CSRF token missing**
```
Solution: Verify custom middleware is before CsrfViewMiddleware
```

**Error: Module not found**
```
Solution: Activate virtual environment, install dependencies
```

**Error: Port already in use**
```bash
# Find process
lsof -i :8000
# Kill process
kill -9 <PID>
```

---

## Deployment & Production

### Q32: How would you deploy this to production?
**A:**

**Backend (Django):**
```
1. Use production WSGI server (Gunicorn/uWSGI)
2. Set DEBUG = False
3. Use environment variables for secrets
4. Configure PostgreSQL (not SQLite)
5. Set ALLOWED_HOSTS
6. Configure static files (WhiteNoise or S3)
7. Set up SSL/HTTPS
8. Use production email backend (SendGrid/AWS SES)
9. Enable database connection pooling
10. Set up logging and monitoring
```

**Frontend (Next.js):**
```
1. Build: npm run build
2. Deploy to Vercel/Netlify
3. Set NEXT_PUBLIC_API_URL to production API
4. Configure environment variables
5. Set up CDN
6. Enable caching
```

**Infrastructure:**
```
- Backend: AWS EC2 / DigitalOcean / Heroku
- Database: AWS RDS / DigitalOcean Managed Database
- Frontend: Vercel / Netlify
- Email: SendGrid / AWS SES
- Monitoring: Sentry / DataDog
```

### Q33: What production settings would you change?
**A:**

```python
# settings.py (production)

DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'api.yourdomain.com']

# Security
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', 5432),
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('SENDGRID_USERNAME')
EMAIL_HOST_PASSWORD = os.environ.get('SENDGRID_API_KEY')

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# CORS
CORS_ALLOWED_ORIGINS = [
    'https://yourdomain.com',
]

# Allauth
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
HEADLESS_FRONTEND_URLS = {
    'account_confirm_email': 'https://yourdomain.com/auth/verify-email/{key}',
}
```

### Q34: How would you handle scaling?
**A:**

**Horizontal scaling:**
- Multiple Django instances behind load balancer
- Use Redis for shared cache
- Use Celery for async tasks
- CDN for static files
- Database read replicas

**Performance optimization:**
- Database indexing
- Query optimization (select_related, prefetch_related)
- Caching (Redis, Memcached)
- Rate limiting
- Connection pooling

**Monitoring:**
- Application monitoring (Sentry)
- Performance monitoring (New Relic)
- Log aggregation (ELK stack)
- Uptime monitoring (Pingdom)

### Q35: What's your testing strategy?
**A:**

**Backend tests:**
```python
# test_auth.py
from django.test import TestCase

class AuthTestCase(TestCase):
    def test_signup(self):
        response = self.client.post('/_allauth/browser/v1/auth/signup', {
            'email': 'test@example.com',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 200)

    def test_login(self):
        # Create user
        # Test login
        # Verify token returned
        pass
```

**Frontend tests:**
```typescript
// auth.test.ts
import { render, screen, fireEvent } from '@testing-library/react';

test('login form submits correctly', async () => {
  render(<LoginPage />);

  fireEvent.change(screen.getByLabelText('Email'), {
    target: { value: 'test@example.com' }
  });

  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'password123' }
  });

  fireEvent.click(screen.getByText('Sign in'));

  // Assert redirect or success message
});
```

**Integration tests:**
```python
# Test complete flow
def test_signup_to_login_flow(self):
    # 1. Signup
    # 2. Verify email
    # 3. Login
    # 4. Access protected endpoint
    # 5. Logout
    pass
```

---

## Bonus Questions

### Q36: What would you improve in this project?
**A:**
1. Add comprehensive testing (unit, integration, e2e)
2. Implement token refresh mechanism
3. Add social OAuth (Google, GitHub)
4. Implement 2FA flow
5. Add rate limiting middleware
6. Implement account recovery
7. Add user profile management
8. Implement WebSockets for real-time updates
9. Add comprehensive logging
10. Create admin dashboard

### Q37: How is this better than using Firebase Auth or Auth0?
**A:**

**Advantages:**
- ✅ Full control over data and logic
- ✅ No vendor lock-in
- ✅ No per-user pricing
- ✅ Can customize everything
- ✅ Learn authentication deeply
- ✅ Own infrastructure

**Disadvantages:**
- ❌ More setup time
- ❌ Need to maintain security
- ❌ Handle compliance yourself

**Best for:**
- Learning projects
- Custom requirements
- Cost-sensitive applications
- Full control needed

### Q38: What did you learn building this?
**A:**
1. **Security**: CSRF, CORS, token-based auth
2. **Architecture**: Separation of concerns, modular design
3. **Django**: ORM, middleware, settings configuration
4. **React/Next.js**: Context API, hooks, routing
5. **API design**: RESTful principles, error handling
6. **TypeScript**: Type safety, interfaces
7. **Deployment**: Virtual environments, environment variables
8. **Problem-solving**: Debugging CORS/CSRF issues

---

## Quick Reference Commands

```bash
# Backend
cd firstproject
source venv/bin/activate
python manage.py runserver
python manage.py migrate
python manage.py createsuperuser

# Frontend
cd frontend
npm run dev
npm run build

# Both
./start-backend.sh
./start-frontend.sh
```

---

**Good luck with your interview! 🚀**

This system demonstrates:
- ✅ Fullstack development skills
- ✅ Security best practices
- ✅ Modern architecture patterns
- ✅ Problem-solving abilities
- ✅ Clean, maintainable code
