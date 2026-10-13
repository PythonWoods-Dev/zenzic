# Home

- [Architecture](architecture/index.md)
- [Spec](specs/spec1.md)

This fixture demonstrates Z412 traceability enforcement: specifications
under `specs/**` are required to have at least one inbound reference from
`architecture/**`. This project intentionally omits that link so the Z412
finding fires on `specs/spec1.md` when the suite is scanned by the Zenzic
engine during a standard `zenzic check all` invocation.
