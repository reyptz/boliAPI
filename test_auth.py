"""
Script de test complet pour les endpoints auth de BoliAPI.
Teste le flow : signup -> signin -> profile -> forgot -> reset -> 2fa -> logout -> CRUD admin
"""

import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001/api/v1"
RESULTS = []


def api(method, path, body=None, token=None):
    """Helper pour appeler l'API."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return resp.status, result
    except urllib.error.HTTPError as e:
        try:
            body_err = json.loads(e.read())
        except Exception:
            body_err = {"detail": str(e)}
        return e.code, body_err


def test(name, status, result, expected_status=None):
    """Log un test."""
    ok = expected_status is None or status == expected_status
    icon = "PASS" if ok else "FAIL"
    RESULTS.append((name, ok))
    print(f"  [{icon}] {name} -> HTTP {status}")
    if not ok:
        print(f"         Expected {expected_status}, got {status}")
        print(f"         Body: {json.dumps(result, indent=2, default=str)[:200]}")
    return result


# ======================================================================
print("\n=== 1. SIGNUP ===")
# ======================================================================

# 1a. Signup avec phone + password
s, r = api("POST", "/auth/signup", {
    "phone": "+22370000001",
    "password": "MonMotDePasse123",
    "role": "client"
})
r1 = test("Signup phone+password", s, r, 201)
user1_token = r1.get("access_token")
user1_id = r1.get("user_id")

# 1b. Signup avec email + PIN
s, r = api("POST", "/auth/signup", {
    "email": "admin@boli.ml",
    "username": "admin_boli",
    "password": "AdminSecure2026",
    "role": "admin"
})
r2 = test("Signup email+username (admin)", s, r, 201)
admin_token = r2.get("access_token")
admin_id = r2.get("user_id")

# 1c. Signup doublon (doit echouer)
s, r = api("POST", "/auth/signup", {
    "phone": "+22370000001",
    "password": "AutreMotDePasse"
})
test("Signup doublon phone (409)", s, r, 409)

# 1d. Signup sans identifiant
s, r = api("POST", "/auth/signup", {"password": "test1234"})
test("Signup sans identifiant (400)", s, r, 400)

# ======================================================================
print("\n=== 2. SIGNIN ===")
# ======================================================================

# 2a. Signin par phone
s, r = api("POST", "/auth/signin", {
    "identifier": "+22370000001",
    "password": "MonMotDePasse123"
})
test("Signin phone+password", s, r, 200)

# 2b. Signin par username
s, r = api("POST", "/auth/signin", {
    "identifier": "admin_boli",
    "password": "AdminSecure2026"
})
test("Signin username+password", s, r, 200)

# 2c. Signin mauvais password
s, r = api("POST", "/auth/signin", {
    "identifier": "+22370000001",
    "password": "MauvaisMDP"
})
test("Signin mauvais password (401)", s, r, 401)

# 2d. Signin user inexistant
s, r = api("POST", "/auth/signin", {
    "identifier": "inexistant@nowhere.com",
    "password": "test"
})
test("Signin user inexistant (404)", s, r, 404)

# ======================================================================
print("\n=== 3. PROFIL ===")
# ======================================================================

# 3a. Get my profile
s, r = api("GET", "/users/me", token=user1_token)
test("GET /users/me", s, r, 200)

# 3b. Update my profile
s, r = api("PUT", "/users/me", {
    "username": "moussa_client"
}, token=user1_token)
test("PUT /users/me (add username)", s, r, 200)

# 3c. Get without token (401)
s, r = api("GET", "/users/me")
test("GET /users/me sans token (401)", s, r, 401)

# ======================================================================
print("\n=== 4. FORGOT / RESET PASSWORD ===")
# ======================================================================

# 4a. Forgot password
s, r = api("POST", "/auth/forgot-password", {
    "identifier": "+22370000001"
})
r4 = test("Forgot password", s, r, 200)
reset_token = r4.get("debug_token")

# 4b. Reset password
if reset_token:
    s, r = api("POST", "/auth/reset-password", {
        "token": reset_token,
        "new_password": "NouveauMDP2026"
    })
    test("Reset password", s, r, 200)

    # 4c. Signin avec nouveau password
    s, r = api("POST", "/auth/signin", {
        "identifier": "+22370000001",
        "password": "NouveauMDP2026"
    })
    test("Signin avec nouveau MDP", s, r, 200)
    user1_token = r.get("access_token")  # refresh token
else:
    print("  [SKIP] Pas de reset token (debug mode off?)")

# ======================================================================
print("\n=== 5. 2FA ===")
# ======================================================================

# 5a. Enable 2FA
s, r = api("POST", "/auth/2fa/enable", token=user1_token)
r5 = test("Enable 2FA", s, r, 200)
totp_secret = r5.get("secret")

# 5b. Verify 2FA (avec pyotp)
if totp_secret:
    import sys
    sys.path.insert(0, ".venv/Lib/site-packages")
    import pyotp
    code = pyotp.TOTP(totp_secret).now()

    s, r = api("POST", "/auth/2fa/verify", {"code": code}, token=user1_token)
    test("Verify 2FA (activation)", s, r, 200)
    user1_token = r.get("access_token")  # new token after 2FA

    # 5c. Signin should now require 2FA
    s, r = api("POST", "/auth/signin", {
        "identifier": "+22370000001",
        "password": "NouveauMDP2026"
    })
    r5c = test("Signin requires 2FA", s, r, 200)

    if r5c.get("requires_2fa"):
        temp_token = r5c.get("temp_token")
        code = pyotp.TOTP(totp_secret).now()
        s, r = api("POST", "/auth/2fa/verify", {"code": code}, token=temp_token)
        test("Complete 2FA signin", s, r, 200)
        user1_token = r.get("access_token")

    # 5d. Disable 2FA
    code = pyotp.TOTP(totp_secret).now()
    s, r = api("POST", "/auth/2fa/disable", {"code": code}, token=user1_token)
    test("Disable 2FA", s, r, 200)

# ======================================================================
print("\n=== 6. ADMIN CRUD ===")
# ======================================================================

# 6a. List users (admin)
s, r = api("GET", "/users?page=1&page_size=10", token=admin_token)
test("GET /users (admin list)", s, r, 200)
if s == 200:
    print(f"         Total users: {r.get('total')}")

# 6b. Get user by ID (admin)
s, r = api("GET", f"/users/{user1_id}", token=admin_token)
test("GET /users/:id (admin)", s, r, 200)

# 6c. Update user (admin)
s, r = api("PUT", f"/users/{user1_id}", {
    "role": "driver"
}, token=admin_token)
test("PUT /users/:id (admin change role)", s, r, 200)

# 6d. Non-admin trying admin endpoint (403)
s, r = api("GET", "/users", token=user1_token)
test("GET /users non-admin (403)", s, r, 403)

# ======================================================================
print("\n=== 7. LOGOUT ===")
# ======================================================================

s, r = api("POST", "/auth/logout", token=user1_token)
test("Logout", s, r, 200)

# Vérifier que le token est invalide après logout
s, r = api("GET", "/users/me", token=user1_token)
test("GET /users/me after logout (401)", s, r, 401)

# ======================================================================
print("\n=== 8. REFRESH TOKEN ===")
# ======================================================================

# Re-signin pour tester le refresh
s, r = api("POST", "/auth/signin", {
    "identifier": "admin_boli",
    "password": "AdminSecure2026"
})
refresh = r.get("refresh_token")

if refresh:
    s, r = api("POST", "/auth/refresh", {"refresh_token": refresh})
    test("Refresh token", s, r, 200)

# ======================================================================
# SUMMARY
# ======================================================================
print(f"\n{'='*50}")
passed = sum(1 for _, ok in RESULTS if ok)
total = len(RESULTS)
print(f"RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("ALL TESTS PASSED!")
else:
    failed = [name for name, ok in RESULTS if not ok]
    print(f"FAILED: {', '.join(failed)}")
print(f"{'='*50}\n")
