# GitLab Omnibus Configuration for Argus Insight
# Reference: https://docs.gitlab.com/omnibus/settings/configuration.html

# ─── External URL ─────────────────────────────────────────────────────────────
# Change this to your actual domain in production
external_url 'http://gitlab.argus.local'

# ─── GitLab Rails ─────────────────────────────────────────────────────────────
gitlab_rails['time_zone'] = 'Asia/Seoul'
gitlab_rails['gitlab_shell_ssh_port'] = 2224

# Initial root password (change after first login)
gitlab_rails['initial_root_password'] = 'Argus!nsight2026'

# API rate limiting
gitlab_rails['rate_limiting_response_text'] = 'Retry later'

# ─── OAuth / OmniAuth (SSO) ──────────────────────────────────────────────────
# Enable OmniAuth for SSO integration with Argus Insight
gitlab_rails['omniauth_enabled'] = true
gitlab_rails['omniauth_allow_single_sign_on'] = ['openid_connect']
gitlab_rails['omniauth_block_auto_created_users'] = false
gitlab_rails['omniauth_auto_link_user'] = ['openid_connect']

# Uncomment and configure for OpenID Connect (e.g., Keycloak, Argus SSO)
# gitlab_rails['omniauth_providers'] = [
#   {
#     name: "openid_connect",
#     label: "Argus SSO",
#     args: {
#       name: "openid_connect",
#       scope: ["openid", "profile", "email"],
#       response_type: "code",
#       issuer: "https://sso.argus.local/realms/argus",
#       discovery: true,
#       client_auth_method: "query",
#       uid_field: "preferred_username",
#       pkce: true,
#       client_options: {
#         identifier: "gitlab",
#         secret: "YOUR_CLIENT_SECRET",
#         redirect_uri: "http://gitlab.argus.local/users/auth/openid_connect/callback"
#       }
#     }
#   }
# ]

# ─── Nginx ────────────────────────────────────────────────────────────────────
nginx['listen_port'] = 80
nginx['listen_https'] = false

# ─── PostgreSQL (embedded) ────────────────────────────────────────────────────
postgresql['shared_buffers'] = "256MB"
postgresql['max_worker_processes'] = 4

# ─── Puma ─────────────────────────────────────────────────────────────────────
puma['worker_processes'] = 2
puma['min_threads'] = 1
puma['max_threads'] = 4

# ─── Sidekiq ──────────────────────────────────────────────────────────────────
sidekiq['max_concurrency'] = 10

# ─── Monitoring ───────────────────────────────────────────────────────────────
# Prometheus metrics endpoint (for Argus monitoring integration)
gitlab_rails['monitoring_whitelist'] = ['0.0.0.0/0']
prometheus['enable'] = false
# grafana['enable'] = false  # Removed in GitLab 17.x (unsupported config)

# ─── Container Registry ──────────────────────────────────────────────────────
# Disabled by default; enable if you need GitLab Container Registry
registry['enable'] = false

# ─── GitLab Pages ─────────────────────────────────────────────────────────────
pages_external_url nil
gitlab_pages['enable'] = false

# ─── Backup ───────────────────────────────────────────────────────────────────
gitlab_rails['backup_keep_time'] = 604800
