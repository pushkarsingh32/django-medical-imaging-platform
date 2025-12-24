# Django + Next.js Authentication - Granular Technical Deep Dive

## Table of Contents
1. [Request/Response Lifecycle](#requestresponse-lifecycle)
2. [Token Generation & Validation](#token-generation--validation)
3. [Database Schema Deep Dive](#database-schema-deep-dive)
4. [HTTP Headers & Communication](#http-headers--communication)
5. [Code Execution Flow](#code-execution-flow)
6. [Memory & State Management](#memory--state-management)
7. [Security Mechanisms](#security-mechanisms)
8. [Error Handling & Edge Cases](#error-handling--edge-cases)

---

## Request/Response Lifecycle

### 1. Signup Request - Line by Line

#### Frontend Execution

```typescript
// User clicks signup button
// File: frontend/app/auth/signup/page.tsx, Line 24

const handleSubmit = async (e: FormEvent) => {
  e.preventDefault();  // Prevent form default submission
  setError('');        // Clear previous errors
  setIsSubmitting(true); // Disable button, show loading

  try {
    // Line 30: Call signup function from AuthContext
    await signup(email, password);
    // ↓ Goes to contexts/AuthContext.tsx, Line 58
  }
}

// File: contexts/AuthContext.tsx, Line 58
const signup = async (email: string, password: string) => {
  try {
    // Line 59: Call API wrapper
    const response = await allauth.auth.signup(email, password);
    // ↓ Goes to lib/allauth.ts, Line 83
  }
}

// File: lib/allauth.ts, Line 83
async signup(email: string, password: string) {
  // Line 84: Delegate to HttpClient
  const response = await this.client.request('/auth/signup', 'POST', { email, password });
  // ↓ Goes to Line 46 (HttpClient.request)
}

// File: lib/allauth.ts, Line 46
async request<T>(endpoint: string, method: string = 'GET', body?: any): Promise<AuthResponse<T>> {
  // Line 47-49: Build headers
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  // Line 51-54: Add session token if exists
  const token = this.getToken();
  if (token) {
    headers['X-Session-Token'] = token;
  }

  // Line 56-61: Make HTTP request
  const response = await fetch(`${API_BASE}${API_PREFIX}${endpoint}`, {
    method,                    // 'POST'
    headers,                   // { 'Content-Type': 'application/json' }
    body: JSON.stringify(body), // '{"email":"test@example.com","password":"pass123"}'
    credentials: 'include',    // Include cookies
  });
  // ↓ HTTP Request sent over network
}
```

**Network Request Details:**
```http
POST http://localhost:8000/_allauth/browser/v1/auth/signup HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Origin: http://localhost:3000
Referer: http://localhost:3000/auth/signup
Accept: application/json

{"email":"test@example.com","password":"password123"}
```

#### Backend Reception

```python
# Django receives request
# Entry point: WSGI/ASGI server → Django middleware stack

# 1. SecurityMiddleware (settings.py Line 62)
#    - Adds security headers
#    - Checks HTTPS redirect
#    ↓

# 2. CorsMiddleware (settings.py Line 63)
#    - Checks Origin header: "http://localhost:3000"
#    - Validates against CORS_ALLOWED_ORIGINS
#    - Adds CORS headers to response
#    ↓

# 3. SessionMiddleware (settings.py Line 64)
#    - Loads Django session (if exists)
#    - Creates session dict
#    ↓

# 4. CommonMiddleware (settings.py Line 65)
#    - URL processing
#    - Adds trailing slash if needed
#    ↓

# 5. DisableCSRFForAllauthMiddleware (settings.py Line 66)
#    File: firstproject/middleware.py, Line 13

class DisableCSRFForAllauthMiddleware:
    def __call__(self, request):
        # Line 15: Check if allauth endpoint
        if request.path.startswith('/_allauth/'):
            # Line 16: Disable CSRF check for this request
            setattr(request, '_dont_enforce_csrf_checks', True)
        # Line 18: Continue to next middleware
        response = self.get_response(request)
        return response
        ↓

# 6. CsrfViewMiddleware (settings.py Line 67)
#    - Checks _dont_enforce_csrf_checks attribute
#    - SKIPS CSRF validation for this request
#    ↓

# 7. AuthenticationMiddleware (settings.py Line 68)
#    - No user authenticated yet (signup request)
#    - request.user = AnonymousUser
#    ↓

# 8. AccountMiddleware (settings.py Line 69)
#    - Allauth-specific setup
#    ↓

# 9. URL Routing
#    File: firstproject/urls.py, Line 27
#    path('_allauth/', include('allauth.headless.urls'))
#    ↓ Matches '/_allauth/browser/v1/auth/signup'
```

#### Allauth Headless Processing

```python
# File: allauth/headless/account/views.py (in site-packages)

class SignupView(APIView):
    def post(self, request):
        # 1. Parse JSON body
        data = request.data
        # data = {'email': 'test@example.com', 'password': 'password123'}

        # 2. Validate input
        serializer = SignupSerializer(data=data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=400)

        # 3. Create user
        user = serializer.save(request)
        # ↓ Internally calls:

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Hash password using PBKDF2
        from django.contrib.auth.hashers import make_password
        hashed_password = make_password('password123')
        # Result: 'pbkdf2_sha256$600000$abcd1234$hash...'

        # Create user record
        user = User.objects.create(
            email='test@example.com',
            password=hashed_password,
            is_active=True,
            date_joined=timezone.now()
        )
        # ↓ SQL executed:
        """
        INSERT INTO auth_user (
            username, email, password, is_staff, is_active,
            is_superuser, date_joined
        ) VALUES (
            '', 'test@example.com', 'pbkdf2_sha256$600000$...',
            false, true, false, '2025-12-23 09:40:42'
        ) RETURNING id;
        """

        # 4. Create email address record
        from allauth.account.models import EmailAddress
        email_address = EmailAddress.objects.create(
            user=user,
            email='test@example.com',
            verified=False,
            primary=True
        )
        # ↓ SQL:
        """
        INSERT INTO account_emailaddress (
            user_id, email, verified, primary
        ) VALUES (
            1, 'test@example.com', false, true
        );
        """

        # 5. Generate session token
        from allauth.headless.tokens.sessions import SessionTokenStrategy
        strategy = SessionTokenStrategy()

        # Generate random token (64 characters)
        import secrets
        token = secrets.token_urlsafe(48)
        # Result: 'xyz789abc123def456...'

        # Hash token for storage
        from django.contrib.auth.hashers import make_password
        token_hash = make_password(token)

        # Create session record (if using database strategy)
        # Store: user_id, token_hash, created, expires

        # 6. Send verification email
        from allauth.account.models import EmailConfirmationHMAC
        confirmation = EmailConfirmationHMAC(email_address)
        key = confirmation.key
        # key = 'MQ:1vXysk:YV0RAj4hIEyOs4iVlWrI8nnI-2b2_FOIJe8dayY5YG8'

        # Build email
        from django.core.mail import send_mail
        verification_url = f'http://localhost:3000/auth/verify-email/{key}'

        send_mail(
            subject='Please Confirm Your Email Address',
            message=f'Click here to verify: {verification_url}',
            from_email='noreply@example.com',
            recipient_list=['test@example.com'],
        )
        # ↓ In development, prints to console

        # 7. Build response
        response_data = {
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'display': user.email,
                    'has_usable_password': True
                }
            },
            'meta': {
                'session_token': token,
                'is_authenticated': True
            }
        }

        return Response(response_data, status=200)
```

**Response HTTP:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true

{
  "data": {
    "user": {
      "id": 1,
      "email": "test@example.com",
      "display": "test@example.com",
      "has_usable_password": true
    }
  },
  "meta": {
    "session_token": "xyz789abc123def456...",
    "is_authenticated": true
  }
}
```

#### Frontend Processing Response

```typescript
// Back to lib/allauth.ts, Line 63
const data = await response.json();
// data = { data: {...}, meta: {...} }

// Line 65-69: Check for errors
if (!response.ok) {
  throw new Error(data.errors?.[0]?.message || 'Request failed');
}

// Line 71-75: Return structured response
return {
  status: response.status,  // 200
  data: data.data,          // { user: {...} }
  meta: data.meta,          // { session_token: '...' }
};

// Back to lib/allauth.ts, Line 84 (AuthModule.signup)
const response = await this.client.request(...);
// Line 85: Handle token update
this.handleTokenUpdate(response);
// ↓ Line 116

private handleTokenUpdate(response: AuthResponse) {
  if (response.meta?.session_token) {
    // Line 118: Call callback to update token
    this.onTokenUpdate(response.meta.session_token);
    // ↓ Goes to Line 192 (Main class)
  }
}

// Line 203 (AllauthAPI.updateToken)
private updateToken(token: string) {
  // Line 204: Store in memory
  this.sessionToken = token;

  // Line 205: Persist to localStorage
  StorageHelper.set('session_token', token);
  // ↓ Line 25

  static set(key: string, value: string): void {
    if (typeof window !== 'undefined') {
      // Line 27: Actually write to browser storage
      localStorage.setItem(key, value);
      // Now: localStorage['session_token'] = 'xyz789abc123def456...'
    }
  }
}

// Back to contexts/AuthContext.tsx, Line 59
const response = await allauth.auth.signup(email, password);

// Line 60-62: Update React state
if (response.data.user) {
  setUser(response.data.user);
  // Triggers re-render of all components using AuthContext
}

// Back to app/auth/signup/page.tsx, Line 31
router.push('/dashboard');
// Navigates to dashboard page
```

---

## Token Generation & Validation

### Session Token Creation (Detailed)

```python
# File: allauth/headless/tokens/sessions.py

class SessionTokenStrategy:
    def create_token(self, request, user):
        # 1. Generate random bytes
        import secrets
        random_bytes = secrets.token_bytes(32)
        # random_bytes = b'\x8f\x2a\x4b...' (32 bytes)

        # 2. Encode to URL-safe base64
        import base64
        token = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
        # token = 'jypL3xQm9z...' (44 characters)

        # 3. Hash token for storage (PBKDF2)
        from django.contrib.auth.hashers import make_password
        token_hash = make_password(token, salt=None, hasher='pbkdf2_sha256')
        # Internally:
        # - Generate random salt: 'abcd1234'
        # - Iterations: 600,000 (Django 5.x default)
        # - Hash function: SHA256
        # - Result: 'pbkdf2_sha256$600000$abcd1234$hash_output...'

        # 4. Store session in database
        from django.contrib.sessions.models import Session
        session = Session.objects.create(
            session_key=token_hash[:40],  # Django session key (40 chars)
            session_data=self._encode_session_data({
                'user_id': user.id,
                'created': timezone.now().isoformat(),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'ip_address': self._get_client_ip(request),
            }),
            expire_date=timezone.now() + timezone.timedelta(hours=24)
        )

        # 5. Return plaintext token to client
        return token  # Only time plaintext exists

    def _get_client_ip(self, request):
        # Get real IP (handle proxies)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
```

### Token Validation (Per Request)

```python
# File: allauth/headless/rest_framework/authentication.py

class SessionTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # 1. Extract token from header
        token = request.headers.get('X-Session-Token')
        if not token:
            return None  # Anonymous user

        # 2. Hash the incoming token
        from django.contrib.auth.hashers import check_password

        # 3. Look up session
        from django.contrib.sessions.models import Session
        try:
            # Find session by checking all sessions
            # (In production, would use custom table with indexed token hash)
            sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            )

            for session in sessions:
                session_data = session.get_decoded()

                # Check if token matches
                # This is simplified - actual implementation uses token table
                if check_password(token, session.session_key):
                    # 4. Token valid! Get user ID from session data
                    user_id = session_data.get('user_id')

                    # 5. Load user
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    user = User.objects.get(id=user_id)

                    # 6. Check user is active
                    if not user.is_active:
                        raise AuthenticationFailed('User inactive')

                    # 7. Attach to request
                    return (user, None)

        except Session.DoesNotExist:
            raise AuthenticationFailed('Invalid token')

        return None

# check_password internally:
def check_password(password, encoded):
    # encoded = 'pbkdf2_sha256$600000$salt$hash'
    algorithm, iterations, salt, hash_value = encoded.split('$', 3)

    # Re-hash the provided token with same salt and iterations
    new_hash = pbkdf2(password, salt, int(iterations), algorithm)

    # Constant-time comparison (prevent timing attacks)
    return constant_time_compare(hash_value, new_hash)
```

---

## Database Schema Deep Dive

### auth_user Table

```sql
CREATE TABLE auth_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    password VARCHAR(128) NOT NULL,           -- 'pbkdf2_sha256$600000$salt$hash'
    last_login DATETIME NULL,
    is_superuser BOOLEAN NOT NULL DEFAULT 0,
    username VARCHAR(150) NOT NULL UNIQUE,    -- Often empty for email-only auth
    first_name VARCHAR(150) NOT NULL,
    last_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,              -- 'test@example.com'
    is_staff BOOLEAN NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    date_joined DATETIME NOT NULL
);

-- Example row:
-- id=1, password='pbkdf2_sha256$600000$abc$xyz', username='',
-- email='test@example.com', is_active=1, date_joined='2025-12-23 09:40:42'
```

### account_emailaddress Table

```sql
CREATE TABLE account_emailaddress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                 -- Foreign key to auth_user.id
    email VARCHAR(254) NOT NULL,              -- 'test@example.com'
    verified BOOLEAN NOT NULL DEFAULT 0,      -- 0 = not verified, 1 = verified
    primary BOOLEAN NOT NULL DEFAULT 0,       -- Primary email flag

    FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE,
    UNIQUE (email),                           -- Email can only exist once
    UNIQUE (user_id, email)                   -- User can't have duplicate emails
);

-- Example row:
-- id=1, user_id=1, email='test@example.com', verified=0, primary=1
```

### Django Sessions Table

```sql
CREATE TABLE django_session (
    session_key VARCHAR(40) PRIMARY KEY,      -- Hashed token (40 chars)
    session_data TEXT NOT NULL,               -- Base64 encoded JSON
    expire_date DATETIME NOT NULL
);

CREATE INDEX django_session_expire_date_idx ON django_session(expire_date);

-- Example row:
-- session_key='abc123def456...',
-- session_data='eyJ1c2VyX2lkIjoxLCJjcmVhdGVkIjoiMjAyNS0xMi0yM1QwOTo0MDo0MiJ9',
-- expire_date='2025-12-24 09:40:42'

-- Decoded session_data:
-- {"user_id": 1, "created": "2025-12-23T09:40:42", "ip_address": "127.0.0.1"}
```

### SQL Queries During Signup

```sql
-- 1. Check if email already exists
SELECT * FROM account_emailaddress WHERE email = 'test@example.com';
-- Result: Empty (no duplicate)

-- 2. Create user
INSERT INTO auth_user (
    password, last_login, is_superuser, username, first_name,
    last_name, email, is_staff, is_active, date_joined
) VALUES (
    'pbkdf2_sha256$600000$salt$hash', NULL, 0, '', '', '',
    'test@example.com', 0, 1, '2025-12-23 09:40:42.123456'
);
-- Returns: id = 1

-- 3. Create email address
INSERT INTO account_emailaddress (user_id, email, verified, primary)
VALUES (1, 'test@example.com', 0, 1);

-- 4. Create session
INSERT INTO django_session (session_key, session_data, expire_date)
VALUES (
    'abc123def456...',
    'base64_encoded_data',
    '2025-12-24 09:40:42'
);

-- Transaction committed
COMMIT;
```

### SQL Queries During Login

```sql
-- 1. Find user by email
SELECT * FROM auth_user
WHERE email = 'test@example.com' AND is_active = 1;
-- Returns: User object

-- 2. Verify password (in Python, not SQL)
-- check_password('password123', user.password)

-- 3. Update last_login
UPDATE auth_user
SET last_login = '2025-12-23 10:00:00'
WHERE id = 1;

-- 4. Create new session
INSERT INTO django_session (session_key, session_data, expire_date)
VALUES (...);

COMMIT;
```

---

## HTTP Headers & Communication

### Frontend → Backend Request Headers

```http
POST /_allauth/browser/v1/auth/login HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Content-Length: 58
Origin: http://localhost:3000
Referer: http://localhost:3000/auth/login
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)
Accept: application/json, text/plain, */*
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br
Connection: keep-alive
X-Session-Token: xyz789abc123def456...

{"email":"test@example.com","password":"password123"}
```

**Header Breakdown:**

| Header | Purpose | Value |
|--------|---------|-------|
| Host | Target server | localhost:8000 |
| Content-Type | Body format | application/json |
| Origin | Request origin (CORS) | http://localhost:3000 |
| Referer | Page that made request | http://localhost:3000/auth/login |
| X-Session-Token | Authentication | Token from localStorage |
| Accept | Response types accepted | application/json |

### Backend → Frontend Response Headers

```http
HTTP/1.1 200 OK
Date: Mon, 23 Dec 2025 09:40:42 GMT
Server: WSGIServer/0.2 CPython/3.11.0
Content-Type: application/json
Content-Length: 234
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: x-session-token, content-type
Vary: Origin
X-Content-Type-Options: nosniff
X-Frame-Options: DENY

{"data":{"user":{...}},"meta":{"session_token":"..."}}
```

**Header Breakdown:**

| Header | Purpose | Why It's There |
|--------|---------|----------------|
| Access-Control-Allow-Origin | CORS | Allows localhost:3000 to read response |
| Access-Control-Allow-Credentials | CORS | Allows cookies/tokens |
| Access-Control-Allow-Headers | CORS | Allows custom X-Session-Token header |
| X-Content-Type-Options | Security | Prevents MIME sniffing |
| X-Frame-Options | Security | Prevents clickjacking |
| Vary: Origin | Caching | Cache separately per origin |

### CORS Preflight (OPTIONS Request)

```http
OPTIONS /_allauth/browser/v1/auth/signup HTTP/1.1
Host: localhost:8000
Origin: http://localhost:3000
Access-Control-Request-Method: POST
Access-Control-Request-Headers: content-type, x-session-token
```

**Response:**
```http
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: POST, GET, OPTIONS
Access-Control-Allow-Headers: content-type, x-session-token
Access-Control-Max-Age: 86400
Content-Length: 0
```

---

## Code Execution Flow

### Middleware Execution Order

```python
# Request flows DOWN through middleware
# Response flows UP through middleware

Request → ┌──────────────────────────────────────┐
          │ 1. SecurityMiddleware                │
          │    - Sets security headers           │
          │    - HSTS, SSL redirect              │
          ├──────────────────────────────────────┤
          │ 2. CorsMiddleware                    │
          │    - Check Origin header             │
          │    - Validate against allowed list   │
          │    - Add CORS headers                │
          ├──────────────────────────────────────┤
          │ 3. SessionMiddleware                 │
          │    - Load session from cookie/db     │
          │    - Create request.session dict     │
          ├──────────────────────────────────────┤
          │ 4. CommonMiddleware                  │
          │    - URL normalization               │
          │    - APPEND_SLASH handling           │
          ├──────────────────────────────────────┤
          │ 5. DisableCSRFForAllauthMiddleware   │
          │    - If path == '/_allauth/':        │
          │      request._dont_enforce_csrf = True│
          ├──────────────────────────────────────┤
          │ 6. CsrfViewMiddleware                │
          │    - Check _dont_enforce_csrf        │
          │    - If True: SKIP validation        │
          │    - If False: Check CSRF token      │
          ├──────────────────────────────────────┤
          │ 7. AuthenticationMiddleware          │
          │    - Try to get user from session    │
          │    - Or run authentication backends  │
          │    - Set request.user                │
          ├──────────────────────────────────────┤
          │ 8. AccountMiddleware (allauth)       │
          │    - Allauth-specific setup          │
          ├──────────────────────────────────────┤
          │         URL Routing                  │
          │    - Match URL pattern               │
          │    - Call view function              │
          ├──────────────────────────────────────┤
          │         View Processing              │
          │    - SignupView.post()               │
          │    - Process request                 │
          │    - Return Response                 │
          └──────────────────────────────────────┘
Response← (Same middleware in reverse order)
```

### Authentication Backend Chain

```python
# settings.py
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# On request with X-Session-Token header:

# 1. AuthenticationMiddleware runs
request.user = None

# 2. Try each backend in order
for backend in AUTHENTICATION_BACKENDS:
    user = backend.authenticate(request)
    if user:
        request.user = user
        break

# 3. If no backend returns user:
if not request.user:
    request.user = AnonymousUser()

# 4. View now has request.user
```

---

## Memory & State Management

### Frontend State Flow

```typescript
// 1. Application starts
// Next.js renders app/layout.tsx

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <AuthProvider>  {/* ← Context Provider wraps app */}
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}

// 2. AuthProvider initializes
export function AuthProvider({ children }) {
  // State stored in memory (React)
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // On mount:
    // 1. Read token from localStorage
    allauth.initialize();
    //    ↓
    //    this.sessionToken = localStorage.getItem('session_token');

    // 2. Validate with backend
    refreshSession();
    //    ↓
    //    GET /_allauth/browser/v1/auth/session
    //    Headers: { X-Session-Token: '...' }
    //    ↓
    //    If valid: setUser(response.data.user)
    //    If invalid: setUser(null), clear localStorage

    setIsLoading(false);
  }, []);

  // Value object (re-created on every render)
  const contextValue = {
    user,           // Current user state
    isLoading,      // Loading state
    isAuthenticated: !!user,  // Computed property
    login,          // Function reference
    signup,         // Function reference
    logout,         // Function reference
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// 3. Components consume context
function DashboardPage() {
  // Re-renders when AuthContext value changes
  const { user, isAuthenticated } = useAuth();
  //      ↑ Gets current value from Provider

  return <div>Welcome {user.email}</div>;
}
```

### Memory Locations

```
┌─────────────────────────────────────────────┐
│           Browser Memory                    │
├─────────────────────────────────────────────┤
│  React Component Tree                       │
│  ├─ RootLayout                              │
│  │  └─ AuthProvider                         │
│  │     ├─ user: { id: 1, email: '...' }    │ ← In memory
│  │     ├─ isLoading: false                  │ ← In memory
│  │     └─ DashboardPage                     │
│  │        └─ (reads user from context)      │
├─────────────────────────────────────────────┤
│  localStorage (Persistent)                  │
│  ├─ 'session_token': 'xyz789abc...'        │ ← On disk
├─────────────────────────────────────────────┤
│  allauth singleton (Module scope)           │
│  ├─ sessionToken: 'xyz789abc...'           │ ← In memory
│  ├─ client: HttpClient {...}                │ ← In memory
│  ├─ auth: AuthModule {...}                  │ ← In memory
└─────────────────────────────────────────────┘
```

### Backend Memory

```python
# Django process (single request)

request = HttpRequest()                    # ← Created per request
request.user = User.objects.get(id=1)      # ← Loaded from database
request.session = {...}                    # ← Loaded from django_session table
request.META = {                           # ← HTTP headers
    'HTTP_X_SESSION_TOKEN': 'xyz...',
    'REMOTE_ADDR': '127.0.0.1',
}

# After request completes:
# - request object is garbage collected
# - No state persists between requests
# - Next request creates new request object

# Database connection pool (persistent)
# - Keeps connections open
# - Reused across requests
# - Configured in CONN_MAX_AGE
```

---

## Security Mechanisms

### Password Hashing Deep Dive

```python
# File: django.contrib.auth.hashers

def make_password(password, salt=None, hasher='default'):
    # 1. Select hasher (PBKDF2 with SHA256)
    hasher = get_hasher(hasher)  # PBKDF2PasswordHasher

    # 2. Generate salt (12 random characters)
    if not salt:
        salt = hasher.salt()
        # Result: 'a1b2c3d4e5f6' (random)

    # 3. Hash password
    hash = hasher.encode(password, salt)
    # Internally:

    import hashlib
    import hmac

    iterations = 600000  # Django 5.x default

    # PBKDF2 algorithm
    key = hashlib.pbkdf2_hmac(
        'sha256',           # Hash function
        password.encode(),  # Password bytes
        salt.encode(),      # Salt bytes
        iterations          # Number of iterations
    )

    # Result: 64-byte hash
    hash_hex = key.hex()
    # '7f3a9b2c...' (128 characters)

    # 4. Format: algorithm$iterations$salt$hash
    return f'pbkdf2_sha256${iterations}${salt}${hash_hex}'

# Example output:
# 'pbkdf2_sha256$600000$a1b2c3d4e5f6$7f3a9b2c1d4e5f...'
#  └─algorithm  └─iter └─salt      └─hash (128 chars)
```

**Why 600,000 iterations?**
- Makes brute force slow (each attempt takes ~0.5 seconds)
- Even with GPU, cracking takes years
- Protects against rainbow tables

### Token Security

```python
# Token generation uses cryptographically secure random
import secrets

# secrets.token_urlsafe(48) generates:
# 1. 48 random bytes from os.urandom()
# 2. Base64url encode (URL-safe, no padding)
# 3. Result: 64-character string

# Example:
token = secrets.token_urlsafe(48)
# 'xyz789abc123def456ghi789jkl012mno345pqr678stu901vwx234yz...'

# Entropy: 48 bytes = 384 bits
# Possible combinations: 2^384 ≈ 10^115
# Brute force: Impossible with current technology
```

### Session Hijacking Prevention

```python
# 1. Token stored as hash in database
# - Attacker with database access can't use tokens

# 2. HTTPS only (production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
# - Prevents token interception over network

# 3. IP address tracking (optional)
session_data = {
    'user_id': 1,
    'ip_address': '192.168.1.100'
}
# - Detect if token used from different IP

# 4. User agent validation (optional)
session_data['user_agent'] = request.META.get('HTTP_USER_AGENT')
# - Detect if token used from different browser

# 5. Token expiration
expire_date = timezone.now() + timedelta(hours=24)
# - Limits damage window
```

---

## Error Handling & Edge Cases

### Network Error Handling

```typescript
// lib/allauth.ts

async request<T>(endpoint: string, method: string, body?: any) {
  try {
    const response = await fetch(API_BASE + endpoint, {...});

    // Handle HTTP errors
    if (!response.ok) {
      const data = await response.json();

      // Structured error from backend
      if (data.errors && data.errors.length > 0) {
        throw new Error(data.errors[0].message);
      }

      // Generic HTTP error
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();

  } catch (error) {
    // Network errors (connection failed, timeout, etc.)
    if (error instanceof TypeError) {
      throw new Error('Network error. Please check your connection.');
    }

    // JSON parse errors
    if (error instanceof SyntaxError) {
      throw new Error('Invalid response from server.');
    }

    // Re-throw other errors
    throw error;
  }
}
```

### Backend Error Handling

```python
# allauth/headless/account/views.py

class SignupView(APIView):
    def post(self, request):
        try:
            # Validate input
            serializer = SignupSerializer(data=request.data)
            if not serializer.is_valid():
                # Return structured errors
                return Response({
                    'errors': [
                        {
                            'message': 'A user is already registered with this email.',
                            'code': 'email_already_exists',
                            'param': 'email'
                        }
                    ]
                }, status=400)

            # Create user
            user = serializer.save(request)

            # ... rest of signup logic

        except IntegrityError as e:
            # Database constraint violation
            return Response({
                'errors': [{
                    'message': 'Database error occurred.',
                    'code': 'integrity_error'
                }]
            }, status=500)

        except Exception as e:
            # Unexpected errors
            logger.error(f'Signup error: {str(e)}', exc_info=True)
            return Response({
                'errors': [{
                    'message': 'An unexpected error occurred.',
                    'code': 'internal_error'
                }]
            }, status=500)
```

### Edge Cases Handled

**1. Duplicate Email:**
```python
# Database constraint ensures uniqueness
# account_emailaddress.email = UNIQUE

# If user tries to signup with existing email:
try:
    EmailAddress.objects.create(email='existing@example.com')
except IntegrityError:
    return error('Email already exists')
```

**2. Token Expiration:**
```python
# On every request:
session = Session.objects.get(session_key=token_hash)

if session.expire_date < timezone.now():
    # Session expired
    session.delete()
    raise AuthenticationFailed('Session expired')
```

**3. Concurrent Logins:**
```python
# Multiple logins create multiple sessions
# Each device has its own token
# Logout on one device doesn't affect others

# To logout all devices:
Session.objects.filter(
    session_data__contains=f'"user_id": {user.id}'
).delete()
```

**4. Email Verification Key Expiry:**
```python
# EmailConfirmationHMAC.key includes timestamp
# Format: 'MQ:1vXysk:signature'
#          │  └─timestamp (base36)
#          └─email_id

# On verification:
confirmation = EmailConfirmationHMAC.from_key(key)
if confirmation.key_expired():
    raise ValidationError('Verification link expired')
```

**5. Password Reset Race Condition:**
```python
# Multiple reset requests create multiple keys
# All keys valid until used
# Once password changed, all keys invalidated

# PasswordResetKey.objects.filter(
#     user=user,
#     created__lt=timezone.now() - timedelta(days=3)
# ).delete()
```

**6. CORS Preflight Cache:**
```python
# Access-Control-Max-Age: 86400
# Browser caches preflight for 24 hours
# No OPTIONS request needed for 24 hours
```

---

This technical deep dive covers the granular, line-by-line execution flow of your authentication system. Use this to explain exactly how each part works in your interview! 🚀
