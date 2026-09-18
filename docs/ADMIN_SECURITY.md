# 🛡️ Administrator Security & Role-Based Access Control

## 1. Rule: "Админ панель только у админов"
The admin panel (`admin_panel.html`) is strictly protected and isolated:
1. **Frontend Gate:** By default, unauthenticated users see a secure credential challenge modal requiring admin credentials or token.
2. **Backend Enforcement:** The Express API routes (`/api/admin/users`, `/api/admin/models`) reject non-admin callers with `403 Forbidden`.
3. **UI Visibility:** The admin panel link is hidden in the main UI (`index.html`) unless the user is logged in as an owner/admin (`admin` or `B3B3097`).

## 2. Authentication Methods
- Admin Credentials (`admin` / default master key)
- Owner GitHub Token (`ghp_*`) matching owner whitelist
- Signed HMAC Admin Session Bearer Tokens (`admin_token_*`)

## 3. Capabilities Restricted to Admins
- User balance adjustments and account tier modifications.
- Account blocking and deletion.
- Private storage synchronization triggers (`B3B3097/Storage-VIBE-CODE`).
- System audit log inspection.
