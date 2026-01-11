# Agent Instructions

This document provides instructions for an AI agent working with the `pyairtable` codebase.

## Getting Started

To get started, you'll need to set up a development environment. This project uses `tox` to manage virtual environments and dependencies.

1.  **Install dependencies:**

    ```bash
    make setup
    ```

    This will install `tox` and `pre-commit` hooks.

2.  **Activate the virtual environment:**

    `tox` creates virtual environments for different Python versions. To see the available environments, run:

    ```bash
    tox -l
    ```

    To activate a specific environment, you can use `source`:

    ```bash
    source .tox/<envname>/bin/activate
    ```

## Running Tests

This project uses `pytest` for testing. You can run the tests using `tox`:

```bash
make test
```

This will run the tests against all configured Python versions.

To run tests for a specific environment, you can use the `-e` flag:

```bash
tox -e py39
```

## Contributing

When contributing to this project, please follow these guidelines:

1.  **Create a new branch** for your changes.
2.  **Write tests** for any new features or bug fixes.
3.  **Ensure all tests pass** before submitting a pull request.
4.  **Update the documentation** if you make any changes to the public API.
5.  **Format your code** using `black`:

    ```bash
    make format
    ```

## Code Style

This project uses `black` for code formatting. Please ensure your code is formatted before submitting a pull request. You can use the `make format` command to automatically format your code.
