#!/usr/bin/env python3
"""Find large GitHub organizations ranked by public member count."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Seed list of suspected large organizations
CANDIDATE_ORGS = [
    # Tech companies - major
    "microsoft",
    "google",
    "facebook",
    "meta",
    "amazon",
    "apple",
    "netflix",
    "twitter",
    "x",
    "uber",
    "airbnb",
    "linkedin",
    "spotify",
    "stripe",
    "shopify",
    "salesforce",
    "oracle",
    "ibm",
    "intel",
    "nvidia",
    "amd",
    "redhat",
    "vmware",
    "cisco",
    "adobe",
    "autodesk",
    "atlassian",
    "jetbrains",
    "mozilla",
    "brave",
    "vercel",
    "netlify",
    "cloudflare",
    "digitalocean",
    "heroku",
    "twilio",
    "datadog",
    "elastic",
    "mongodb",
    "hashicorp",
    "confluent",
    "databricks",
    "snowflake",
    "palantir",
    "pinterest",
    "dropbox",
    "slack",
    "zoom",
    "okta",
    "splunk",
    "newrelic",
    "pagerduty",
    "grafana",
    "sentry-io",
    "snyk",
    # Tech companies - more
    "square",
    "block",
    "paypal",
    "coinbase",
    "robinhood",
    "plaid",
    "postman",
    "kong",
    "redislabs",
    "timescale",
    "influxdata",
    "planetscale",
    "supabase",
    "appwrite",
    "hasura",
    "prisma",
    "auth0",
    "temporal-io",
    # Open source foundations & communities
    "apache",
    "linux",
    "linuxfoundation",
    "cncf",
    "kubernetes",
    "docker",
    "openstack",
    "eclipse",
    "gnome",
    "kde",
    "freedesktop",
    "w3c",
    "whatwg",
    "tc39",
    "nodejs",
    "denoland",
    "rust-lang",
    "golang",
    "python",
    "ruby",
    "php",
    "dotnet",
    "openjdk",
    "swift",
    "kotlin",
    "flutter",
    "reactjs",
    "vuejs",
    "angular",
    "sveltejs",
    "emberjs",
    "django",
    "rails",
    "laravel",
    "spring-projects",
    "quarkusio",
    "openjs-foundation",
    "jquery",
    "expressjs",
    "nestjs",
    "fastify",
    # More languages & runtimes
    "elixir-lang",
    "erlang",
    "haskell",
    "ocaml",
    "clojure",
    "scala",
    "crystal-lang",
    "nim-lang",
    "zig",
    "vlang",
    # Cloud & infrastructure
    "aws",
    "azure",
    "googlecloudplatform",
    "terraform-providers",
    "pulumi",
    "ansible",
    "puppet",
    "chef",
    "jenkinsci",
    "circleci",
    "github",
    "gitlab",
    "gitea",
    "sourcegraph",
    "argoproj",
    "fluxcd",
    "tektoncd",
    "crossplane",
    "istio",
    "envoyproxy",
    "traefik",
    "nginx",
    "containerd",
    "containers",
    "rancher",
    "prometheus-community",
    "thanos-io",
    "grafana",
    "open-telemetry",
    "jaegertracing",
    "fluentd",
    # Data & ML
    "tensorflow",
    "pytorch",
    "keras-team",
    "scikit-learn",
    "pandas-dev",
    "numpy",
    "scipy",
    "jupyter",
    "huggingface",
    "openai",
    "langchain-ai",
    "mlflow",
    "dbt-labs",
    "airbyte",
    "apache-airflow",
    "dagster-io",
    "streamlit",
    "plotly",
    "dask",
    "polars",
    # Databases
    "postgres",
    "postgresql",
    "mysql",
    "mariadb",
    "cockroachdb",
    "yugabyte",
    "redis",
    "scylladb",
    "neo4j",
    "arangodb",
    "dgraph-io",
    "couchbase",
    "duckdb",
    "sqlite",
    # Security
    "owasp",
    "aquasecurity",
    "falcosecurity",
    "sigstore",
    # Gaming
    "unity-technologies",
    "godotengine",
    "epicgames",
    "valvesoftware",
    "bevyengine",
    "libgdx",
    "raylib",
    # Blockchain
    "ethereum",
    "bitcoin",
    "solana-labs",
    "cosmos",
    "polkadot",
    "near",
    "aptos-labs",
    "chainlink",
    "uniswap",
    "openzeppelin",
    # Media & design
    "gimp",
    "inkscape",
    "blender",
    "darktable",
    "obs-project",
    "audacity",
    "musescore",
    # Universities & research
    "stanford",
    "mit",
    "berkeley",
    "cmu",
    "harvard",
    "princeton",
    "caltech",
    "gatech",
    "uiuc",
    "deepmind",
    "google-research",
    "facebookresearch",
    # Other large communities
    "home-assistant",
    "freecodecamp",
    "exercism",
    "mdn",
    "discourse",
    "matrix-org",
    "forem",
    "signal",
    "element-hq",
    "wordpress",
    "drupal",
    "magento",
    "ghost",
    "strapi",
    "directus",
    "sanity-io",
    # Package managers & build tools
    "npm",
    "yarnpkg",
    "pnpm",
    "pypa",
    "rubygems",
    "gradle",
    "maven",
    "bazel",
    "cmake",
    "webpack",
    "rollup",
    "esbuild",
    "swc",
    "turbo",
    "nx",
    # Testing
    "selenium",
    "cypress-io",
    "playwright",
    "puppeteer",
    "jest",
    "vitest",
    "pytest-dev",
    "junit-team",
    "testing-library",
    "storybook",
    # CLI & terminal
    "charmbracelet",
    "alacritty",
    "ohmyzsh",
    "fish-shell",
    "nushell",
    # Editors & IDEs
    "neovim",
    "vim",
    "vscode",
    "gitpod",
    "helix-editor",
    "zed-industries",
    # DevOps & SRE
    "kubernetes-sigs",
    "operator-framework",
    "helm",
    "kustomize",
    "terraform",
    "terragrunt",
    "ansible-collections",
    "packer",
    "vagrant",
    "nomad",
    # China tech
    "alibaba",
    "aliyun",
    "tencentcloud",
    "tencent",
    "baidu",
    "bytedance",
    "didi",
    "meituan",
    "jd",
    "xiaomi",
    "huawei",
    "ant-design",
    "element-plus",
    "vant-ui",
    # India tech
    "razorpay",
    "zerodha",
    "flipkart",
    "swiggy",
    "zomato",
    # Europe tech
    "klarna",
    "adyen",
    "deliveroo",
    "transferwise",
    "wise",
    "contentful",
    "celonis",
    "uipath",
    # Japan tech
    "line",
    "mercari",
    "cyberagent",
    "rakuten",
    "yahoo-japan",
    # More orgs that might be large
    "SAP",
    "sap",
    "siemens",
    "bosch",
    "philips",
    "sony",
    "samsung",
    "lg",
    "htc",
    "motorola",
    "lenovo",
    "dell",
    "hp",
    "accenture",
    "infosys",
    "tcs",
    "wipro",
    "cognizant",
    "redhat-developer",
    "ibm-cloud",
    "oracle-devrel",
    "awslabs",
    "aws-samples",
    "azure-samples",
    "GoogleCloudPlatform",
    "actions",
    "cli",
    "desktop",
    "electron",
    "atom",
    "vercel-community",
    "prisma-community",
]


def get_public_member_count(org):
    """Get the public member count for an organization."""
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"/orgs/{org}/public_members",
                "--paginate",
                "-q",
                "length",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return org, 0, result.stderr.strip()

        total = sum(
            int(line) for line in result.stdout.strip().split("\n") if line
        )
        return org, total, None

    except subprocess.TimeoutExpired:
        return org, 0, "timeout"
    except Exception as e:
        return org, 0, str(e)


def main():
    # Dedupe the list (case-insensitive)
    seen = set()
    unique_orgs = []
    for org in CANDIDATE_ORGS:
        lower = org.lower()
        if lower not in seen:
            seen.add(lower)
            unique_orgs.append(org)

    print(
        f"Querying public member counts for {len(unique_orgs)}"
        " candidate organizations..."
    )
    print("(This may take a few minutes)\n")

    results = []
    errors = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(get_public_member_count, org): org
            for org in unique_orgs
        }

        completed = 0
        for future in as_completed(futures):
            completed += 1
            org, count, error = future.result()
            if error:
                errors.append((org, error))
            else:
                results.append((org, count))

            sys.stdout.write(
                f"\rProcessed {completed}/{len(unique_orgs)} orgs"
            )
            sys.stdout.flush()

    print("\n")

    # Sort by member count descending
    results.sort(key=lambda x: x[1], reverse=True)

    # Show orgs with 100+ members
    large_orgs = [(org, count) for org, count in results if count >= 100]

    print("=== Organizations with 100+ public members ===\n")
    print(f"{'Rank':<6} {'Organization':<30} {'Public Members':>15}")
    print("-" * 55)

    for i, (org, count) in enumerate(large_orgs, 1):
        print(f"{i:<6} {org:<30} {count:>15,}")

    print(f"\nFound {len(large_orgs)} organizations with 100+ public members")

    # Also show next tier (50-99)
    mid_orgs = [(org, count) for org, count in results if 50 <= count < 100]
    if mid_orgs:
        print("\n\n=== Organizations with 50-99 public members ===\n")
        print(f"{'Rank':<6} {'Organization':<30} {'Public Members':>15}")
        print("-" * 55)
        for i, (org, count) in enumerate(mid_orgs, len(large_orgs) + 1):
            print(f"{i:<6} {org:<30} {count:>15,}")


if __name__ == "__main__":
    main()
