# Session 1 transcript — api-gateway, rate limiting

**user:** One client sent 12k req/min last week and starved every other tenant.
We need per-token rate limiting on the public API. Before you touch anything:
do not break the existing response schema, and do not add third-party
dependencies beyond redis-py — we already vendor that.

**assistant:** Understood. Let me map the request path first.

**assistant:** `ls src/gateway/`
```
__init__.py  middleware.py  server.py  routing.py  auth.py
```

**assistant:** `sed -n '1,40p' src/gateway/server.py`
The ASGI app is built in `src/gateway/server.py`. Every request passes through
`apply_middleware()` at line 31, which is the only place middleware is
composed. There is no rate limiter registered today.

**assistant:** `sed -n '1,60p' src/gateway/middleware.py`
`src/gateway/middleware.py` holds four middlewares, all following the same
shape: a class with an `async def __call__(self, scope, receive, send)`.
Anything I add has to match that signature or `apply_middleware()` will not
compose it.

**assistant:** `grep -rn "token" src/gateway/auth.py | head`
The per-request API token is resolved in `src/gateway/auth.py` and attached to
`scope["state"]["token_id"]`. That is the key to limit on — not the client IP,
which is behind a shared load balancer and therefore useless for isolation.

**user:** Good. What about storage?

**assistant:** `cat config/redis.yaml`
There is already a Redis instance configured at `config/redis.yaml`, pool size
32, and `redis-py` is vendored. So the limiter can keep its counters there
without any new dependency.

**assistant:** I want to reproduce the starvation before changing anything.

**assistant:** `python -m tools.loadgen --rps 200 --duration 60 --token demo-a`
Reproduced it on `main@a1b2c3d`. With one client at 200 rps, p95 latency for
every other token goes from 180ms to 4.2s. The worker pool is shared and
saturates. This is the regression we need to prevent.

**user:** Any traps?

**assistant:** Two.

First, `apply_middleware()` composes in registration order and the auth
middleware must run *before* the limiter, otherwise `scope["state"]["token_id"]`
is not populated yet and every request looks anonymous.

**assistant:** Second, a fixed-window counter will let a client send 2x the
limit across a window boundary. With 200 rps that is enough to starve the pool
again, so it has to be a sliding window.

**assistant:** `cat config/limits.yaml`
```
cat: config/limits.yaml: No such file or directory
```
The per-token limits file does not exist yet. It needs to be created, and the
limiter should read defaults from it rather than hardcoding them.

**user:** How will we know it works?

**assistant:** A regression test that fails on main: drive two tokens through
the gateway, assert the noisy one gets 429s while the quiet one keeps its
latency. I would put it in `tests/test_rate_limit.py` and run it with
`pytest tests/test_rate_limit.py -q`.

**user:** We are out of budget for this session. Hand it off.
