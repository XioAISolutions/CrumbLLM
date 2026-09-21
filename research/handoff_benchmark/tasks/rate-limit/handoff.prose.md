Continuing the api-gateway rate-limiting work. The goal is per-token rate
limiting so one client cannot starve the shared worker pool — limit on the
token, not the client IP, since everything sits behind a shared load balancer.

The limiter belongs in src/gateway/middleware.py, matching the existing
`async def __call__(self, scope, receive, send)` shape, and gets registered in
apply_middleware() in src/gateway/server.py. It must be registered after the
auth middleware, because src/gateway/auth.py is what populates
scope["state"]["token_id"] — register it earlier and every request looks
anonymous. Use a sliding window, not a fixed window: a fixed window lets a
client burst 2x the limit across a boundary, which is enough to starve the
pool again.

Counters go in the Redis already configured at config/redis.yaml. Per-token
limits should be read from config/limits.yaml, which does not exist yet and
needs creating.

Constraints: do not break the existing response schema, and add no third-party
dependencies beyond redis-py.

Starvation was reproduced on main@a1b2c3d — one client at 200 rps takes every
other token's p95 from 180ms to 4.2s. Verify the fix with a regression test at
tests/test_rate_limit.py, run as `pytest tests/test_rate_limit.py -q`.
