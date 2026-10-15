# Security and spending boundaries

- All output archive paths are POSIX-relative; reject '..', absolute paths, drives, duplicate destinations, and unexpected file extensions for cutouts.
- Source files must resolve under the configured input directory. The MCP service accepts only filenames from PREHNITE_HOME/requests and PREHNITE_HOME/profiles.
- The local MCP server uses stdio and does not expose a listening network port or public file URLs.
- Paid API inference is disabled by default. Both allow_paid and a positive maximum USD budget plus per-stage estimates are required. Cloud uploads require additional authorization.
- Costs are estimated reserves, not verified invoices. fal queue calls can be charged even when result retrieval fails; persist remote request IDs and never retry an ambiguous submission automatically.
- No secrets in manifests or Git. Use environment variables and secret managers locally. Do not upload private images without user permission.
- Remote artifacts must use HTTPS and the allowlisted fal media domain; cap downloads. Treat external file metadata and masks as untrusted.
- Agents may submit configured jobs but must not execute arbitrary commands or access arbitrary filesystem paths.
- For public or multi-user deployments, add user authentication, per-user budgets, job ownership, request-rate limits, process locking and encrypted storage before exposing the service.
- Generated images and cutouts may contain errors. Technical validation is not proof of semantic correctness.
