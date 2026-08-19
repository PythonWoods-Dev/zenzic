---
description: "Design and architectural philosophy behind the Zenzic Language Server (ZLS)."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Language Server Architecture (ZLS)

The Zenzic Language Server (ZLS) implements the Language Server Protocol (LSP) to bring the "Hostile Precision" feedback loop directly into the authoring environment. This document explains the architectural constraints and design decisions behind its foundation.

---

## The Zero-Dependency JSON-RPC Dispatcher

A fundamental constraint of Zenzic is to remain lean and fast. While the Python ecosystem offers comprehensive LSP libraries (such as `pygls` or `lsprotocol`), integrating them would violate our zero-inference and dependency-minimal invariants.

Instead, Zenzic ships with a bespoke JSON-RPC 2.0 dispatcher built entirely on the Python standard library. The dispatcher sits over standard input/output (`stdio`) byte streams and handles framing robustly. By reading chunks based exactly on the `Content-Length` header, it is resilient to network or buffer fragmentation without blocking indefinitely.

---

## The Incremental Document Manager (Zero-DBT Enforcement)

The Zenzic philosophy mandates **Zero-DBT** (Zero Documented Technical Debt). The system must scale optimally and perform with $O(N)$ guarantees from Day 1.

Rather than relying on `TextDocumentSyncKind.Full` (which transmits the entire document across the IPC boundary on every keystroke, introducing O(N) transport overhead), the ZLS enforces **Incremental Sync** (`TextDocumentSyncKind.Incremental = 2`).

### UTF-16 Code Unit Synchronization

Implementing incremental synchronization correctly in Python poses a specific technical challenge: **character encodings**. The LSP specification dictates that character offsets are expressed in UTF-16 code units, not Unicode scalar values or UTF-8 bytes.

In Python, strings are conceptually sequences of Unicode scalar values. This means a surrogate-pair emoji (like 📝) counts as a single character in a Python string, but consumes two UTF-16 code units according to the LSP protocol.

The `DocumentManager` resolves this impedance mismatch by parsing the string linearly, counting two columns for code points beyond the Basic Multilingual Plane (BMP) (`> 0xFFFF`). This guarantees that textual patches sent by the editor client apply with absolute mathematical precision over the in-memory document state, preventing silent desynchronization between what the author sees and what Zenzic analyzes.

---

## Debounced Diagnostic Emission

To protect the host CPU, ZLS implements a single-threaded **Debounced Diagnostic Emission** strategy. Running the AST validation engine synchronously on every `didChange` keystroke introduces unacceptable computational overhead, scaling poorly on large 10,000+ line documents.

ZLS solves this entirely within the standard synchronous loop via manual stream buffering and `select.select` I/O multiplexing:

1. **State Decoupling:** `didChange` events apply incremental patches instantly but only mark the document as `dirty`, stamping it with the current timestamp.
2. **Yield & Multiplex:** The server waits for new `stdio` payloads using `select` with a strict `100ms` timeout.
3. **Execution:** The Zenzic Engine is only invoked to run validation rules if the document has been `dirty` for at least `300ms`.

This guarantees $O(1)$ transport ingestion overhead during rapid typing, unleashing the $O(N)$ rule engine only during genuine cognitive pauses from the author.

---

## Global Topological Awareness (VSM)

To enforce structural rules like `Z101` (Broken Link) or `Z104` (File Not Found), the server requires global topological awareness of the repository.

Consistent with the **Zero-Threading Policy** to prevent race conditions and GIL unpredictability, ZLS constructs and maintains the Virtual Site Map (VSM) synchronously:

1. **Synchronous Initialization:** During the `initialized` phase, ZLS performs an initial read of the workspace to build the complete VSM. This temporarily blocks the $I/O$ multiplexer but safely loads the topological state into memory.
2. **Incremental Patching ($O(1)$):** ZLS registers the `workspace/didChangeWatchedFiles` capability to instruct the language client to monitor the filesystem for changes. When a file is created, updated, or deleted, ZLS receives an event and patches the dictionary-based VSM in strictly $O(1)$ time.

This ensures that the language server remains highly responsive and strictly single-threaded while accurately validating cross-file structural integrity in real-time.

---

## See Also

- [Core Architecture](./architecture.md)
