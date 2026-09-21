# Releasing

Install friction is the single largest fixable loss in this project's funnel.
Every documented install is a git URL today, and a git URL costs you the people
who will type `pip install crumb-llm` and nothing else. This is the checklist
that ends that, in dependency order.

## 0. The blocker, stated plainly

`crumb-llm` has **never been registered on PyPI**, and `crumb-format` serves
**0.2.0**, which predates `crumb_core`. So:

```console
$ pip install crumb-llm            # 404 — the name is unregistered
$ pip install crumb-format         # installs 0.2.0, which has no crumb_core
$ pip install git+…/CrumbLLM       # fails: crumb-format>=1.2.0 does not exist on PyPI
```

Nothing in this repository can fix that. It needs a PyPI account with upload
rights, which CI does not have and this checklist cannot conjure.

## 1. Release `crumb-format` 1.2.0 first

CrumbLLM depends on `crumb-format>=1.2.0` for `crumb_core`. Until that exists on
PyPI, a CrumbLLM release is unusable no matter how it is built.

In the [`crumb-format`](https://github.com/XioAISolutions/crumb-format)
repository, on `main`, with `crumb_core` present:

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*   # rehearse first
python -m twine upload dist/*
```

Verify from a clean environment before going further:

```bash
python -m venv /tmp/v && /tmp/v/bin/pip install "crumb-format>=1.2.0"
/tmp/v/bin/python -c "import crumb_core; print(crumb_core.WIRE_VERSION)"
```

## 2. Delete the workarounds this repository carries for that gap

Once step 1 is on PyPI, three things here become lies and should go:

- the two `Install crumb-format from source (pre-release of 1.2.0)` steps in
  `.github/workflows/ci.yml`, which both carry a comment saying to delete them;
- the two-command install block in `README.md` between the
  `<!-- install:start -->` markers, which becomes a single
  `pip install crumb-llm`;
- the "`pip install crumb-format` alone is not enough today" paragraph in the
  `ImportError` raised by `crumb_llm/crumb/parser_adapter.py`.

The `quickstart` CI job runs whatever is between those README markers, so it
will tell you if you change the prose and not the reality, or the reverse.

## 3. Release `crumb-llm`

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

`.github/workflows/publish.yml` already publishes on a tag, so in practice:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

## 4. Prove the thing you just told people to run

From a machine that has never seen this repository:

```bash
python -m venv /tmp/fresh
/tmp/fresh/bin/pip install crumb-llm
/tmp/fresh/bin/crumblm score examples/weak-handoff.crumb   # expect 0.29, exit 0
/tmp/fresh/bin/crumb-eja --help
```

A release is not done when the upload succeeds. It is done when that block runs
clean somewhere that is not your laptop.

## 5. Then, and only then, announce

A launch into a broken install is worse than no launch: the traffic arrives
once. `docs/LESSONS_FROM_LAYA.md` §4.4 is the case study — Laya's viral days
carried three "cannot reproduce the quickstart" issues, and they were closed in
hours because someone was watching.
