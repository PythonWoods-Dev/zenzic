import os
from pathlib import Path

# Mapping of file to its related relative link and text
files = {
    "docs/developers/explanation/core-laws.md": ("../../reference/zenzic-style.md", "Zenzic Style Guide"),
    "docs/developers/explanation/governance/lpgp.md": ("../../how-to/contribute/pull-requests.md", "Contributing Pull Requests"),
    "docs/developers/explanation/governance/technical-debt.md": ("../../../reference/finding-codes.md", "Finding Codes Index"),
    "docs/developers/explanation/mdx-asset-rationale.md": ("../../reference/zenzic-style.md", "Zenzic Style Guide"),
    "docs/developers/explanation/sovereign-verification-model.md": ("../../reference/adapter-api.md", "Adapter API Reference"),
    "docs/developers/explanation/tailwind-mkdocs-bridge.md": ("../../../how-to/use-brand-system.md", "Brand System Guidelines"),
    "docs/developers/how-to/contribute/pull-requests.md": ("../../reference/zenzic-style.md", "Zenzic Style Guide"),
    "docs/developers/how-to/contribute/report-a-bug.md": ("./pull-requests.md", "Contributing Pull Requests"),
    "docs/developers/how-to/contribute/report-a-docs-issue.md": ("./pull-requests.md", "Contributing Pull Requests"),
    "docs/developers/reference/adapter-examples.md": ("./adapter-api.md", "Adapter API Reference"),
    "docs/developers/reference/ast-foundations.md": ("../../explanation/architecture.md", "Core Architecture"),
    "docs/developers/reference/credential-scanner-obligations.md": ("../../../reference/finding-codes.md", "Finding Codes Index"),
    "docs/developers/reference/supply-chain-assurance-profile.md": ("../how-to/contribute/pull-requests.md", "Contributing Pull Requests"),
    "docs/explanation/baseline-tracking.md": ("../reference/cli.md", "CLI Reference"),
    "docs/explanation/brand-philosophy.md": ("../how-to/use-brand-system.md", "Brand System Guidelines"),
    "docs/explanation/configuration-loading.md": ("../how-to/initialize-configuration.md", "Initialize Configuration"),
    "docs/explanation/core-mechanics.md": ("./architecture.md", "Core Architecture"),
    "docs/explanation/exclusion-design.md": ("../how-to/manage-cross-site-links.md", "Manage Cross-Site Links"),
    "docs/explanation/language-server-architecture.md": ("./architecture.md", "Core Architecture"),
    "docs/explanation/mineral-path.md": ("../how-to/migrate-engines.md", "Migrating Engines"),
    "docs/explanation/scoring-system.md": ("../reference/scoring-algorithm.md", "Scoring Algorithm"),
    "docs/explanation/why-zenzic.md": ("./architecture.md", "Core Architecture"),
    "docs/how-to/add-badges.md": ("../reference/cli.md", "CLI Reference"),
    "docs/how-to/configure-ci-cd.md": ("../reference/cli.md", "CLI Reference"),
    "docs/how-to/configure-social-metadata.md": ("../explanation/why-zenzic.md", "Why Zenzic"),
    "docs/how-to/initialize-configuration.md": ("../explanation/configuration-loading.md", "Configuration Loading"),
    "docs/reference/api-json.md": ("./cli.md", "CLI Reference"),
    "docs/reference/checks.md": ("./finding-codes.md", "Finding Codes Index"),
}

for filepath, (link, text) in files.items():
    p = Path(filepath)
    if not p.exists():
        print(f"NOT FOUND: {filepath}")
        continue
    
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"\n\n## See Also\n\n- [{text}]({link})\n")
    print(f"Appended to {filepath}")

