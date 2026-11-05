<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Integration Setup

This guide explains how to connect to the data platform API.

## Authentication

Configure the SDK with your AWS credentials:

```yaml
provider: aws
region: us-east-1
access_key: AKIAIOSFODNN7EXAMPLE1234
secret_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

> **Security note:** This is a documentation example demonstrating Z201
> CREDENTIAL_SECRET detection. Replace example values with your actual
> credentials via environment variables — never commit real keys to version
> control.

## Next Steps

- See `docs/configuration.md` for advanced options.
- Run `zenzic check references` to scan for secrets in your own docs.
