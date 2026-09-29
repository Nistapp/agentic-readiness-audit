# Widget Service

Widget Service exposes a small HTTP API for managing widgets. It is written for teams that need
a dependable, boring service they can extend without reading the whole repository first.

## Running it

Install Python 3.11 or newer, then start the service from a checkout. Configuration lives in
environment variables documented in the example environment file. The service listens on port
8080 by default and stores state on disk under the data directory.

## Contributing

Open a pull request against the main branch and make sure the test suite passes before you ask
for review. Changes that alter the public API should update the documentation in the same change
set.
