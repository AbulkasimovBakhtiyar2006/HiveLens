# Railway deployment

The Docker image uses Python 3.12 and the tested dependency lock. It listens on
`0.0.0.0:$PORT`; Railway checks `/healthz`. Attach one persistent volume at `/data`
and keep one replica: this prototype stores records in JSON files, not a shared DB.
The bundled benchmark and public illustrations remain available when `/data` is empty.

## Required variables

- `HIVELENS_AUTH_USER`: login name, e.g. `judge`.
- `HIVELENS_AUTH_PASSWORD`: a unique random password, at least 16 characters.
- `MODEL_API_KEY`: the owner's Meta Model API credential, only in Railway variables.
- `HIVELENS_API_IPV6=1`: use IPv6 for the model client. Also enable and apply
  **Outbound IPv6** in Railway Networking. Our deployment returned model-not-found
  over IPv4 while the same key and requests succeeded over IPv6. Local installs
  keep the default network selection unless explicitly configured otherwise.
- `HIVELENS_PUBLIC_READ=1`: allow visitors to browse saved records, images, exports,
  study data and benchmarks without a password. All POST writes/model calls and
  job streams still require owner sign-in. Enable only for data intended to be public.
- `HIVELENS_IMPORT_STUDY=1`: optionally import the attributed historical Serra da
  Lousa study apiary in Production at startup; repeated imports preserve inspections.

The image sets `HIVELENS_REQUIRE_AUTH=1`, `HIVELENS_SECURE_COOKIES=1`,
`HIVELENS_OPEN_BROWSER=0` and `HIVELENS_DATA_DIR=/data`. Do not disable authentication
or secure cookies on the public service. Use the Railway HTTPS domain.

## Scope of the protection

This is a **shared, password-protected judging workspace**, not a multi-tenant product.
Anyone with the password can see its records, change settings and run billable model
calls. Use only public samples or photos intended for this audience. The API key is
never returned to the browser. New photo analyses send images to the Meta Model API.

Sessions expire after eight hours. Cookies are signed, HttpOnly, Secure and SameSite=Lax;
cross-origin writes are rejected. Sign out clears the browser cookie. Rotating the
password invalidates all existing sessions. Login attempts are limited by the socket
peer, which may be shared by visitors behind Railway's proxy.

By default only `/healthz` and the sign-in page are public. With `HIVELENS_PUBLIC_READ=1`,
the UI and explicitly allowed read APIs, images and exports are public. Owner profile
details are omitted for guests; profile photos and job streams remain private.
Changing data and running models always require a session. The deployment archive/image exclude local `.env`, private hive
data, model caches, IDE files and demo-video production assets.

Deployment is billed under the Railway account's existing plan; model calls are
billed separately by the API provider. Set account usage limits according to your
budget. This setup does not automatically purchase a plan or change account limits.

## Local container check

Set a strong password before starting; do not commit it:

```bash
docker build -t hivelens .
docker run --rm -p 8080:8080 -v hivelens-data:/data \
  -e HIVELENS_AUTH_PASSWORD -e MODEL_API_KEY \
  -e HIVELENS_SECURE_COOKIES=0 hivelens
```

The cookie override above is for local HTTP only. Railway HTTPS must retain Secure.
