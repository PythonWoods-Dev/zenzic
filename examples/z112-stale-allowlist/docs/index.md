# Welcome

Check out the [Guide](guide.md) for more details. This fixture illustrates
how an `absolute_path_allowlist` entry becomes stale once no scanned link
still references its path prefix. The leftover configuration no longer
protects anything and should be pruned during routine maintenance,
alongside any other unused entries discovered in the same audit pass.
