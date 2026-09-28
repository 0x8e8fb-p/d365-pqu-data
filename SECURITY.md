# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability. Use GitHub's private vulnerability reporting feature for this repository when available, or contact the repository owner through a private GitHub channel.

## Security model

- The published dataset and GitHub Pages site are read-only.
- The sync workflow uses only the built-in GitHub token.
- No Microsoft Graph, SharePoint, Azure, database, or third-party API credentials are required.
- Dependencies and GitHub Actions are locked or pinned and updated through Dependabot.
- Source Markdown is treated as untrusted input and parsed into a bounded, validated schema.
- The dashboard renders text with DOM APIs, never as HTML, and accepts only https links from source text.
- Both HTML pages carry a Content-Security-Policy that allows only the site's own scripts and styles plus the build-time hash of the inline theme script; the site loads nothing from other origins.
- Spreadsheet text values are guarded against formula-style injection.
- Failed updates preserve the last valid published dataset.

Do not put credentials, tokens, customer data, or private Microsoft information in issues, pull requests, logs, fixtures, or generated files.
