# Contributing

Thanks for helping make Uzbek voice AI work offline. Bug reports, Uzbek test sentences, setup notes for new hardware and code changes are all welcome.

## Before you start

- For a bug, open an issue with your OS, CPU/GPU, the command you ran and the full error output.
- For a larger change (a new engine, a new platform, a change to the action whitelist), open an issue first so we can agree on the approach.

## Setup

Follow [First run](README.md#first-run) in the README. In short:

```bash
pnpm run setup
pnpm models:download list
pnpm models:verify
pnpm dev
```

You only need the models for the parts you work on. The unit tests don't load any models.

## Checks

Run these before opening a pull request:

```bash
pnpm test        # web tests + Python unit tests (tests/unit)
pnpm lint
pnpm typecheck
```

## Pull requests

- Keep each pull request to one change, and explain what it does and how you tested it.
- Add or update a unit test in `tests/unit` when you change Python behavior, especially Uzbek text normalization, STT result handling or action planning.
- Never commit model weights, audio recordings of real people or `.env` files.
- Changes to Mac control must keep every action whitelist-validated before it runs.

## Uzbek text

When you add normalization rules (Latin to Cyrillic transliteration, numbers to words), include example sentences in the test so others can see the expected output.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
